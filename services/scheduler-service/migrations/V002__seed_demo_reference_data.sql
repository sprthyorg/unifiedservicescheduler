-- Demo reference data for local / staging only (mirrors app.repositories.memory.seed_demo_data).
-- Production reference data is replicated from dealer-management and CRM systems (A-03);
-- the deploy pipeline excludes this file for production (deploy/README.md).

INSERT INTO dealerships (id, name, timezone) VALUES
  ('DLR-HYD-01', 'Hyderabad Central Motors', 'Asia/Kolkata');

INSERT INTO dealership_hours (dealership_id, weekday, opens_at, closes_at)
SELECT 'DLR-HYD-01', d, '08:00', '18:00' FROM generate_series(1, 6) AS d;

INSERT INTO service_types (id, name, duration_minutes, required_skill, required_bay_capability) VALUES
  ('SVC-OIL',      'Oil & filter change',          60,  'GENERAL',         'LIFT'),
  ('SVC-PERIODIC', 'Periodic maintenance service', 180, 'GENERAL',         'LIFT'),
  ('SVC-ALIGN',    'Wheel alignment',              45,  'ALIGNMENT',       'ALIGNMENT_RIG'),
  ('SVC-EV-BATT',  'EV battery health check',      90,  'EV_HIGH_VOLTAGE', 'EV_SAFE');

INSERT INTO service_bays (id, dealership_id, name, capabilities) VALUES
  ('BAY-01', 'DLR-HYD-01', 'Bay 1',             '{LIFT}'),
  ('BAY-02', 'DLR-HYD-01', 'Bay 2',             '{LIFT}'),
  ('BAY-03', 'DLR-HYD-01', 'Bay 3 (alignment)', '{LIFT,ALIGNMENT_RIG}'),
  ('BAY-04', 'DLR-HYD-01', 'Bay 4 (EV)',        '{LIFT,EV_SAFE}');

INSERT INTO technicians (id, dealership_id, name, skills) VALUES
  ('TEC-001', 'DLR-HYD-01', 'Ravi Kumar',   '{GENERAL}'),
  ('TEC-002', 'DLR-HYD-01', 'Anita Rao',    '{GENERAL,ALIGNMENT}'),
  ('TEC-003', 'DLR-HYD-01', 'Imran Shaikh', '{GENERAL,EV_HIGH_VOLTAGE}');

INSERT INTO technician_shifts (technician_id, weekday, starts_at, ends_at)
SELECT t.id, d, t.s::time, t.e::time
FROM (VALUES ('TEC-001', '08:00', '17:00'), ('TEC-002', '09:00', '18:00'), ('TEC-003', '08:00', '17:00')) AS t(id, s, e)
CROSS JOIN generate_series(1, 6) AS d;

INSERT INTO customers (id, display_name) VALUES
  ('CUS-1001', 'Demo Customer A'),
  ('CUS-1002', 'Demo Customer B');

INSERT INTO vehicles (id, customer_id, vin, make, model, model_year) VALUES
  ('VEH-5001', 'CUS-1001', 'MA3EYD32S00123456', 'Maruti', 'Swift',    2023),
  ('VEH-5002', 'CUS-1002', 'MAT625402P0K12345', 'Tata',   'Nexon EV', 2024);
