-- scheduler-service schema v1.0.0  (04-design/data-model/data-model_v1.0.md)
-- Flyway-style versioned migration. Forward-only; never edit after release — add V00N instead.

CREATE EXTENSION IF NOT EXISTS btree_gist;   -- equality on text inside GiST exclusion constraints

-- ---------------------------------------------------------------- reference data (A-03: replicated)
CREATE TABLE dealerships (
    id          text PRIMARY KEY,
    name        text        NOT NULL,
    timezone    text        NOT NULL,                       -- IANA name, e.g. Asia/Kolkata
    active      boolean     NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE dealership_hours (
    dealership_id text     NOT NULL REFERENCES dealerships(id) ON DELETE CASCADE,
    weekday       smallint NOT NULL CHECK (weekday BETWEEN 1 AND 7),   -- ISO: 1 = Monday
    opens_at      time     NOT NULL,
    closes_at     time     NOT NULL,
    PRIMARY KEY (dealership_id, weekday),
    CHECK (closes_at > opens_at)
);

CREATE TABLE service_types (
    id                       text PRIMARY KEY,
    name                     text     NOT NULL,
    duration_minutes         integer  NOT NULL CHECK (duration_minutes BETWEEN 15 AND 600),
    required_skill           text     NOT NULL,
    required_bay_capability  text     NOT NULL,
    active                   boolean  NOT NULL DEFAULT true
);

CREATE TABLE service_bays (
    id             text PRIMARY KEY,
    dealership_id  text    NOT NULL REFERENCES dealerships(id),
    name           text    NOT NULL,
    capabilities   text[]  NOT NULL DEFAULT '{}',
    active         boolean NOT NULL DEFAULT true
);
CREATE INDEX ix_service_bays_dealership ON service_bays (dealership_id);

CREATE TABLE technicians (
    id             text PRIMARY KEY,
    dealership_id  text    NOT NULL REFERENCES dealerships(id),
    name           text    NOT NULL,
    skills         text[]  NOT NULL DEFAULT '{}',
    active         boolean NOT NULL DEFAULT true
);
CREATE INDEX ix_technicians_dealership ON technicians (dealership_id);

CREATE TABLE technician_shifts (
    technician_id text     NOT NULL REFERENCES technicians(id) ON DELETE CASCADE,
    weekday       smallint NOT NULL CHECK (weekday BETWEEN 1 AND 7),
    starts_at     time     NOT NULL,
    ends_at       time     NOT NULL,
    PRIMARY KEY (technician_id, weekday),
    CHECK (ends_at > starts_at)

);

CREATE TABLE customers (
    id            text PRIMARY KEY,
    display_name  text NOT NULL            -- minimal PII by design (NFR-09)
);

CREATE TABLE vehicles (
    id           text PRIMARY KEY,
    customer_id  text     NOT NULL REFERENCES customers(id),
    vin          char(17) NOT NULL UNIQUE,
    make         text     NOT NULL,
    model        text     NOT NULL,
    model_year   smallint NOT NULL
);
CREATE INDEX ix_vehicles_customer ON vehicles (customer_id);

-- ---------------------------------------------------------------- core aggregate (FR-03)
CREATE TABLE appointments (
    id                   uuid PRIMARY KEY,
    reference            text        NOT NULL UNIQUE,
    customer_id          text        NOT NULL REFERENCES customers(id),
    vehicle_id           text        NOT NULL REFERENCES vehicles(id),
    dealership_id        text        NOT NULL REFERENCES dealerships(id),
    service_type_id      text        NOT NULL REFERENCES service_types(id),
    technician_id        text        NOT NULL REFERENCES technicians(id),
    service_bay_id       text        NOT NULL REFERENCES service_bays(id),
    start_at             timestamptz NOT NULL,
    end_at               timestamptz NOT NULL,
    status               text        NOT NULL CHECK (status IN ('CONFIRMED', 'CANCELLED')),
    idempotency_key      text        NOT NULL,
    request_hash         char(64)    NOT NULL,
    notes                text        CHECK (char_length(notes) <= 500),
    version              integer     NOT NULL DEFAULT 1,
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now(),
    cancelled_at         timestamptz,
    cancellation_reason  text,
    CONSTRAINT ck_appointment_period CHECK (end_at > start_at),
    CONSTRAINT uq_appointment_idempotency UNIQUE (customer_id, idempotency_key),          -- FR-08
    -- NFR-05: zero double-booking, enforced by the database itself (ADR-002)
    CONSTRAINT ex_no_technician_double_booking EXCLUDE USING gist (
        technician_id WITH =, tstzrange(start_at, end_at, '[)') WITH &&
    ) WHERE (status = 'CONFIRMED'),
    CONSTRAINT ex_no_bay_double_booking EXCLUDE USING gist (
        service_bay_id WITH =, tstzrange(start_at, end_at, '[)') WITH &&
    ) WHERE (status = 'CONFIRMED'),
    CONSTRAINT ex_no_vehicle_double_booking EXCLUDE USING gist (
        vehicle_id WITH =, tstzrange(start_at, end_at, '[)') WITH &&
    ) WHERE (status = 'CONFIRMED')
);
-- availability / day-load queries (FR-02, FR-04): confirmed rows of one dealership in a window
CREATE INDEX ix_appointments_dealership_start ON appointments (dealership_id, start_at) WHERE status = 'CONFIRMED';
-- customer history (FR-05)
CREATE INDEX ix_appointments_customer_start ON appointments (customer_id, start_at DESC);

-- ---------------------------------------------------------------- transactional outbox (ADR-004)
CREATE TABLE outbox (
    id              uuid PRIMARY KEY,
    aggregate_id    uuid        NOT NULL,
    event_type      text        NOT NULL,
    schema_version  smallint    NOT NULL,
    payload         jsonb       NOT NULL,
    occurred_at     timestamptz NOT NULL,
    published_at    timestamptz
);
CREATE INDEX ix_outbox_unpublished ON outbox (occurred_at) WHERE published_at IS NULL;
