# Sequences (v1.0)

| ID | Flow | File | Requirements |
|---|---|---|---|
| USS-DSN-SEQ-001 | Book appointment, including replay, conflict and alternatives | `book-appointment_v1.0.mmd` | FR-01, FR-02, FR-03, FR-06, FR-08, FR-09 |
| USS-DSN-SEQ-002 | Cancel appointment | `cancel-appointment_v1.0.mmd` | FR-07 |

Availability (FR-04) is a read-only variant of steps 13–15 of SEQ-001, run for every 15-minute
candidate of the day. It takes no lock and is advisory only.
