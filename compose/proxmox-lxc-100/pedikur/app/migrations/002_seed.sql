-- Without these the app is broken on arrival: no working hours means an
-- unbounded calendar grid and no bookable day.

INSERT INTO working_hours (weekday, start, end, is_closed) VALUES
    (0, '09:00', '17:00', 0),
    (1, '09:00', '17:00', 0),
    (2, '09:00', '17:00', 0),
    (3, '09:00', '17:00', 0),
    (4, '09:00', '17:00', 0);

INSERT INTO setting (key, value) VALUES
    ('buffer_min', '15'),
    ('default_interval_days', '42');
