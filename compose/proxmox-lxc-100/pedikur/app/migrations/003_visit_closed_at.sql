-- When a Visit was first closed, as ISO-8601 UTC.
--
-- Without it, "has this Visit ever been priced" has to be inferred from
-- status, and that inference is wrong the moment a status bounces: a Visit
-- done months ago, mis-tapped to no_show and closed again, would be restamped
-- at today's price, and a price correction typed on the second close would be
-- silently discarded because the guard read the second tap as a retry.
ALTER TABLE visit ADD COLUMN closed_at TEXT;
