# The Reboot That Looked Like a Hang

**Date:** 2026-10-17
**Hostname:** pve (HP EliteDesk 800 G4 SFF, Proxmox VE 9.1)
**IP address:** 192.168.0.109

## Status: fixed

After about seven weeks of uptime, `reboot` on pve seemed to hang. The power light stayed on and the machine was clearly running, but nothing on it answered: no SSH, no web UI, no guests, no DNS from the AdGuard LXC. A power-button reset brought everything back.

It was not a hang. The reboot was clean, and the new boot stopped in **emergency mode** because one USB disk did not show up. The fix makes the two USB data disks optional at boot, and stops mergerfs from writing to the root filesystem while one is missing.

## What the journal showed

The journal is persistent, so the failed boot is there in full. `journalctl --list-boots` shows a boot that lasted under two minutes between the long-running one and the boot after the reset:

```
 -3 049dad1a... Mon 2026-08-31 00:12:44 CEST  Sat 2026-10-17 12:02:50 CEST
 -2 0250fb33... Sat 2026-10-17 12:04:26 CEST  Sat 2026-10-17 12:06:00 CEST
 -1 53a7afd2... Sat 2026-10-17 12:07:36 CEST  Sat 2026-10-17 12:47:57 CEST
```

| Time | What happened |
|---|---|
| 12:01:33 | `The system will reboot now!` |
| 12:01:37-12:02:50 | All guests and services stopped normally, in 77 seconds |
| ~12:03:50 | Firmware (36 s), then the kernel |
| 12:04:26 | systemd starts waiting for `/dev/disk/by-uuid/9d844522-...` (disk3) |
| 12:05:56 | `Timed out waiting for device`, then `Dependency failed for mnt-disk3.mount`, then `Dependency failed for local-fs.target`, then **`Started emergency.service - Emergency Shell`** |
| ~12:06 | Power-button reset |
| 12:07:37 | `Found device ... ST1000LM048-2E7172 Filmek`, and the boot completes |

So the shutdown half was fine, and the box did come back up, as far as an emergency shell. That shell sits on the local console waiting for the root password. It starts no sshd, no `pveproxy` and no guests, which is why everything looked dead from the network.

## Why disk3 was missing

disk3 is a 1 TB USB disk (ST1000LM048, label "Filmek"), one of the two USB data disks in the mergerfs pool. In the good boots the kernel enumerates two SuperSpeed USB devices:

```
usb 2-2: new SuperSpeed USB device number 2 using xhci_hcd
usb 2-9: new SuperSpeed USB device number 3 using xhci_hcd
```

In the failed boot only `usb 2-9` appears. `usb 2-2`, which is disk3, never enumerated at all. A warm reboot does not cut power to the USB enclosure. My best guess is that the enclosure or the drive did not come back after the reset, and a full power cycle fixed it. That is an interpretation of the log, not something I could reproduce.

This disk is already known to be unreliable: `disk3-watchdog.service` checks every 60 seconds and remounts it if it drops. That watchdog could not help here, because it starts after `local-fs.target`, and `local-fs.target` was the unit that failed.

## Why one disk took down the whole host

The fstab line had no `nofail`:

```
UUID=9d844522-61a0-4723-a537-5acf5386eefd  /mnt/disk3  ext4  defaults,noatime  0  2
```

Without `nofail`, the systemd fstab generator makes the mount a hard requirement of `local-fs.target`. systemd waits the default 90 seconds for the device and then fails the target. `local-fs.target` has `OnFailure=emergency.target`, so a missing USB disk, holding only media, stopped the hypervisor and every guest on it from starting.

## The fix

**1. Make the USB data disks optional at boot, with a shorter wait.** disk3 and disk4 are the USB disks. disk1 and disk2 are internal SATA and stay required.

```
UUID=9d844522-61a0-4723-a537-5acf5386eefd  /mnt/disk3  ext4  defaults,noatime,nofail,x-systemd.device-timeout=30s  0  2
UUID=ddb93aeb-d8c8-435f-b3c8-ac8960281eaf  /mnt/disk4  ext4  defaults,noatime,nofail,x-systemd.device-timeout=30s  0  2
```

After `systemctl daemon-reload`, the generator moved both mounts from `local-fs.target.requires` to `local-fs.target.wants`:

```
/run/systemd/generator/local-fs.target.requires/: boot-efi.mount mnt-disk1.mount mnt-disk2.mount mnt-storage.mount -.mount
/run/systemd/generator/local-fs.target.wants/:    mnt-disk3.mount mnt-disk4.mount ...
```

A missing USB disk now costs about 30 seconds of boot time, and the watchdog remounts disk3 once the host is up.

**2. Keep mergerfs off the root filesystem while a branch is missing.** `nofail` brings a risk of its own. The pool is `/mnt/disk1:/mnt/disk3:/mnt/disk4`. If disk3 is not mounted, `/mnt/disk3` is just an empty directory on the 60 GB root filesystem, and mergerfs treats it as a normal branch. With `category.create=mfs`, new files could land on the root filesystem. The fix is to make the bare mountpoint directories immutable. That has to be done underneath the mounted disks, through a bind mount of `/`:

```bash
mkdir -p /run/rootview && mount --bind / /run/rootview
chattr +i /run/rootview/mnt/disk3 /run/rootview/mnt/disk4
touch /run/rootview/mnt/disk3/probe   # Operation not permitted
umount /run/rootview
```

The flag sits on the directory in the root filesystem. Mounting a disk over it is unaffected, so the mounted disk stays writable as normal.

Not tested: whether mergerfs picks up a branch that gets mounted after mergerfs started, without remounting mergerfs. Testing it would mean unmounting a live disk.

## SnapRAID while a disk is missing

The obvious worry is the nightly SnapRAID sync running while disk3 is missing and treating 25,500 files as deleted. Three things prevent that:

- **SnapRAID's own guard.** From `snapraid(1)`: "If SnapRAID detects that all the files originally present on the disk are missing or rewritten, it stops proceeding unless you specify this option" (`-E`, `--force-empty`). The manual says this check exists to catch a data filesystem that is not mounted.
- **The daemon's delete threshold.** `/etc/snapraidd.conf` has `sync_threshold_deletes = 2000`. disk3 holds about 25,500 files, so the 03:00 maintenance sync would refuse anyway. disk4 holds only about 650 files, which is under the threshold, so for disk4 the first guard is the protection.
- **The immutable mountpoint.** Nothing can be written into the empty directory, so SnapRAID cannot mistake new files there for disk3's content.

When the watchdog remounts disk3, every file is back where it was, and the next sync sees no difference. The one thing not to do while a disk is missing is run `snapraid sync -E` by hand.

The UUID check does not help here: with single parity, SnapRAID allows one UUID change by design.

## A mistake made while verifying: `mount -a` stacks mergerfs

To check the edited fstab I ran `mount -a`. For ext4 that is harmless, because already-mounted filesystems are skipped. **A FUSE mount is not recognized as already mounted.** `mount -a` started a second mergerfs process and mounted it on top of the live `/mnt/storage`:

```
55 32 0:40 / /mnt/storage ... fuse.mergerfs 1:3:4 ...
428 55 0:597 / /mnt/storage ... fuse.mergerfs 1:3:4 ...
```

The visible symptom was node_exporter failing every scrape with `collected metric "node_filesystem_size_bytes" ... was collected before with the same name and label values`. A single `umount /mnt/storage` removes the topmost mount and leaves the original underneath. Running containers had bound the original mount at start, so they never saw the stacked one.

On this host, check fstab with `findmnt --verify` and mount one named mountpoint, never `mount -a`.

## Rollback

```bash
cp /etc/fstab.bak-20261017 /etc/fstab
mkdir -p /run/rootview && mount --bind / /run/rootview
chattr -i /run/rootview/mnt/disk3 /run/rootview/mnt/disk4
umount /run/rootview
systemctl daemon-reload
```

## Takeaways

- **"The reboot hung" and "the boot stopped in emergency mode" look identical from the network.** `journalctl --list-boots` tells them apart in a second: a short boot between the old one and the reset means the machine did come back.
- **On a hypervisor, every removable data disk needs `nofail`.** Without it, a media disk can keep every guest from starting.
- **`nofail` on a mergerfs branch needs a guard.** Otherwise the empty mountpoint becomes a writable branch on the root filesystem.
- **A watchdog that starts after `local-fs.target` cannot rescue a failure in `local-fs.target`.**
