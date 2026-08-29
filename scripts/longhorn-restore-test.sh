#!/bin/bash
# Longhorn volume backup restore test - on the volume of a live, running application.
#
# Runs on 109, because this is where kubectl for the K3s cluster is.
#
# WHY IT IS NEEDED WHEN longhorn-backup-check.sh ALREADY EXISTS:
#   That one tells you a backup WAS CREATED and that the BackupTarget is reachable.
#   This script asks whether the backup is READABLE BACK, and whether what comes back
#   is usable by the application. The two are not the same: a successfully uploaded
#   but corrupt or half-drawn backup passes the first one.
#
# WHY IT DOES NOT VERIFY BY CHECKSUM (measured 2026-08-28):
#   The snapshot is taken of a RUNNING application, so it is crash-consistent -
#   exactly as it would be on a node death. On Forgejo's sqlite database the WAL was
#   larger at that moment than the db file itself (4,128,272 vs 1,257,472 bytes).
#   gitea.db on its own is stale without the WAL, so a byte comparison would either
#   have failed, or passed while hiding 4 MB of un-merged WAL. Hence the verdict is
#   whether the APPLICATION'S OWN BINARY opens the restored data directory and finds
#   the expected data in it.
#
# WHAT IT TOUCHES:
#   It only READS the live PVC (snapshot). The application is not stopped and not
#   restarted. It creates and then deletes: a snapshot and a backup named
#   "restore-test-", a StorageClass, a PVC and a pod. It does not touch the
#   RecurringJob's backups - it filters by name prefix.
#
#   With KEEP_BACKUP=1 the snapshot and the backup are kept. By default they are
#   deleted so that repeated runs do not pile up.
#
# ROLLBACK, if it breaks off halfway:
#   kubectl -n $NS delete pod  restore-test-verify --ignore-not-found
#   kubectl -n $NS delete pvc  restore-test-data   --ignore-not-found
#   kubectl delete sc longhorn-restore-test        --ignore-not-found
#   kubectl -n longhorn-system delete backup,snapshot -l restore-test=true
#
# Usage:
#   ./longhorn-restore-test.sh
#   NS=apps PVC=other-data DEPLOY=other ./longhorn-restore-test.sh
#
set -uo pipefail

NS="${NS:-apps}"
PVC="${PVC:-forgejo-data}"
DEPLOY="${DEPLOY:-forgejo}"
MOUNT="${MOUNT:-/var/lib/gitea}"
VERIFY_CMD="${VERIFY_CMD:-forgejo -c $MOUNT/custom/conf/app.ini admin user list}"
VERIFY_MATCH="${VERIFY_MATCH:-Pironex9}"
KEEP_BACKUP="${KEEP_BACKUP:-0}"

TAG="restore-test-$(date +%Y%m%d-%H%M%S)"
RC=1

step() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
fail() { printf '\033[31mHIBA: %s\033[0m\n' "$*"; exit 1; }

command -v kubectl >/dev/null || fail "nincs kubectl"

VOL=$(kubectl -n "$NS" get pvc "$PVC" -o jsonpath='{.spec.volumeName}' 2>/dev/null)
[ -n "$VOL" ] || fail "nem talalom a $NS/$PVC PVC kotetet"
IMG=$(kubectl -n "$NS" get deploy "$DEPLOY" -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null)
[ -n "$IMG" ] || fail "nem talalom a $NS/$DEPLOY deployment image-et"

step "0. Kiindulas"
echo "namespace/PVC:  $NS/$PVC"
echo "kotet:          $VOL"
echo "image:          $IMG"
echo "verify:         $VERIFY_CMD"
echo "keresett minta: $VERIFY_MATCH"

step "1. Snapshot a FUTO koteten (crash-consistent, mint egy node-halal)"
kubectl apply -f - >/dev/null <<EOF || fail "snapshot letrehozas"
apiVersion: longhorn.io/v1beta2
kind: Snapshot
metadata:
  name: $TAG
  namespace: longhorn-system
  labels:
    restore-test: "true"
spec:
  volume: $VOL
  createSnapshot: true
EOF
R=""
for i in $(seq 1 30); do
  R=$(kubectl -n longhorn-system get snapshot "$TAG" -o jsonpath='{.status.readyToUse}' 2>/dev/null)
  [ "$R" = "true" ] && { echo "readyToUse $((i*2))s alatt"; break; }
  sleep 2
done
[ "$R" = "true" ] || fail "a snapshot nem lett ready ($R)"

step "2. Backup a Garage S3-ra"
kubectl apply -f - >/dev/null <<EOF || fail "backup letrehozas"
apiVersion: longhorn.io/v1beta2
kind: Backup
metadata:
  name: $TAG
  namespace: longhorn-system
  labels:
    restore-test: "true"
spec:
  snapshotName: $TAG
EOF
S=""
for i in $(seq 1 150); do
  S=$(kubectl -n longhorn-system get backup "$TAG" -o jsonpath='{.status.state}' 2>/dev/null)
  case "$S" in
    Completed) echo "Completed, $((i*2))s"; break ;;
    Error)     kubectl -n longhorn-system get backup "$TAG" -o jsonpath='{.status.error}'; echo
               fail "a backup hibara futott" ;;
    *)         printf '\r  %s %s%%  (%ss)' "${S:-...}" \
                 "$(kubectl -n longhorn-system get backup "$TAG" -o jsonpath='{.status.progress}' 2>/dev/null)" \
                 "$((i*2))"; sleep 2 ;;
  esac
done
[ "$S" = "Completed" ] || fail "a backup nem fejezodott be idoben ($S)"

URL=$(kubectl -n longhorn-system get backup "$TAG" -o jsonpath='{.status.url}')
[ -n "$URL" ] || fail "ures backup URL"
# `size` is the logical extent of the snapshot, NOT the cost of the backup. Retention
# has to be planned from newlyUploadDataSize - on 2026-08-28 283,115,520 vs 554,286.
printf 'logikai meret (size):      %s bajt\n' "$(kubectl -n longhorn-system get backup "$TAG" -o jsonpath='{.status.size}')"
printf 'ami tenylegesen felment:   %s bajt\n' "$(kubectl -n longhorn-system get backup "$TAG" -o jsonpath='{.status.newlyUploadDataSize}')"
echo "url: $URL"

step "3. StorageClass es PVC a mentesbol"
# numberOfReplicas 1: this is a throwaway verification volume, it needs no redundancy.
kubectl apply -f - >/dev/null <<EOF || fail "restore SC/PVC"
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: longhorn-restore-test
provisioner: driver.longhorn.io
allowVolumeExpansion: true
reclaimPolicy: Delete
parameters:
  numberOfReplicas: "1"
  staleReplicaTimeout: "30"
  fromBackup: "$URL"
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: restore-test-data
  namespace: $NS
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: longhorn-restore-test
  resources:
    requests:
      storage: $(kubectl -n "$NS" get pvc "$PVC" -o jsonpath='{.spec.resources.requests.storage}')
EOF

step "4. Ellenorzo pod - ugyanaz az image, a VISSZAALLITOTT koteten"
kubectl -n "$NS" delete pod restore-test-verify --ignore-not-found >/dev/null
kubectl apply -f - >/dev/null <<EOF || fail "verify pod"
apiVersion: v1
kind: Pod
metadata:
  name: restore-test-verify
  namespace: $NS
spec:
  restartPolicy: Never
  securityContext:
    runAsUser: 1000
    runAsGroup: 1000
    runAsNonRoot: true
    fsGroup: 1000
    seccompProfile: {type: RuntimeDefault}
  containers:
    - name: verify
      image: $IMG
      securityContext:
        allowPrivilegeEscalation: false
        capabilities: {drop: [ALL]}
      command: ["/bin/sh", "-c"]
      args:
        - |
          echo "--- a visszaallitott koteten ---"
          ls -la $MOUNT/data/ 2>/dev/null || ls -la $MOUNT
          echo "--- verify ---"
          $VERIFY_CMD
      volumeMounts:
        - {name: data, mountPath: $MOUNT}
  volumes:
    - name: data
      persistentVolumeClaim:
        claimName: restore-test-data
EOF
PH=""
for i in $(seq 1 120); do
  PH=$(kubectl -n "$NS" get pod restore-test-verify -o jsonpath='{.status.phase}' 2>/dev/null)
  case "$PH" in
    Succeeded|Failed) echo "pod: $PH ($((i*2))s)"; break ;;
    *) printf '\r  %s (%ss)' "${PH:-Pending}" "$((i*2))"; sleep 2 ;;
  esac
done
echo
LOG=$(kubectl -n "$NS" logs restore-test-verify 2>&1)
echo "$LOG"

step "5. Verdikt"
if printf '%s' "$LOG" | grep -q -- "$VERIFY_MATCH"; then
  printf '\033[32mATMENT: a Garage-bol visszaallitott koteten az alkalmazas sajat binarisa megtalalta a(z) "%s" mintat.\033[0m\n' "$VERIFY_MATCH"
  RC=0
else
  printf '\033[31mMEGBUKOTT: a visszaallitott koteten nincs meg a(z) "%s" minta.\033[0m\n' "$VERIFY_MATCH"
  RC=1
fi

step "6. Takaritas"
kubectl -n "$NS" delete pod restore-test-verify --ignore-not-found
kubectl -n "$NS" delete pvc restore-test-data --ignore-not-found
kubectl delete sc longhorn-restore-test --ignore-not-found
if [ "$KEEP_BACKUP" = "1" ]; then
  echo "KEEP_BACKUP=1 - a snapshot es a backup megmarad: $TAG"
else
  kubectl -n longhorn-system delete backup "$TAG" --ignore-not-found
  kubectl -n longhorn-system delete snapshot "$TAG" --ignore-not-found
fi

exit $RC
