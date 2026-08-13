# PERC Response Service - Phase 2 Data Model Specification

## 1. Overview & Source Analysis
The structured data layer for the PERC Response Service is derived from six JSON files located in `MockData/structured/`. These files contain domain information regarding PERC's courses, branch locations, fee structures, eligibility guidelines, availability schedules, and admission status.

### JSON Source Datasets
1. **`courses.json`**: List of 14 course programs with attributes like `id`, `name`, `category`, `target_class`, `subjects` (array), `focus`, `duration`, `batch_size`, `price`, `exams_covered` (array), and `description`.
2. **`branches.json`**: List of campus locations (currently Begur Main Campus) with nested structure for address, geo coordinates, contact info, timings, batch slots, nearby landmarks, and Google Maps URL.
3. **`fees.json`**: Top-level object containing global fee policies, contact info, general fee info (includes array, price range), and a list of program fees matching course IDs.
4. **`eligibility.json`**: Top-level object containing general admission policy, step-by-step admission process (array of objects), demo class info, and program-specific eligibility rules (`program`, `min_class`, `max_class`, `notes`).
5. **`availability.json`**: Top-level object containing institute timings, batch timing slots, 1-on-1 tuition details, and seat availability contact information.
6. **`admission-status.json`**: Top-level object containing `current_status`, admission notes, seat limit per batch, batch slots, free demo info, and contact info for checking availability.

---

## 2. PostgreSQL Relational Schema Design

To ensure clean isolation within shared database environments (such as Supabase PostgreSQL), all tables created for this service will use explicit table names.

### Tables & Columns

#### Table 1: `courses`
Stores all educational offerings.
- `id` (VARCHAR(50), Primary Key) — e.g., 'perc-ignite', 'neet-ug'
- `name` (VARCHAR(150), NOT NULL) — e.g., 'PERC Ignite'
- `category` (VARCHAR(50), NOT NULL, Index) — e.g., 'PERC Core', 'NEET', 'JEE'
- `target_class` (VARCHAR(100), NOT NULL) — e.g., 'Class 6', 'Classes 11-12'
- `subjects` (JSONB, NOT NULL) — Array of subject strings, e.g., ["Mathematics", "Science"]
- `focus` (VARCHAR(255)) — Key focus area description
- `duration` (VARCHAR(50), NOT NULL) — e.g., '1 Year', '2 Years'
- `batch_size` (VARCHAR(50)) — e.g., '15-20 students'
- `price` (VARCHAR(50)) — e.g., 'Contact for price'
- `exams_covered` (JSONB, NOT NULL) — Array of covered exams
- `description` (TEXT) — Detailed course description
- `created_at` (TIMESTAMPTZ, Default NOW())
- `updated_at` (TIMESTAMPTZ, Default NOW())

#### Table 2: `branches`
Stores branch and campus location data.
- `id` (VARCHAR(50), Primary Key) — e.g., 'begur-main'
- `name` (VARCHAR(150), NOT NULL) — Campus name
- `type` (VARCHAR(50), NOT NULL) — e.g., 'Main Campus'
- `address` (JSONB, NOT NULL) — Nested address object (street, area, city, state, pincode, country)
- `geo` (JSONB) — Geo coordinates (latitude, longitude)
- `contact` (JSONB, NOT NULL) — Contact info (phones, email, support_email, whatsapp)
- `timings` (JSONB, NOT NULL) — Operating hours (days, opens, closes, note)
- `batch_slots` (JSONB, NOT NULL) — Available batch slot definitions
- `nearby_landmarks` (JSONB) — Array of landmarks
- `google_maps_url` (TEXT) — Embedded map URL
- `created_at` (TIMESTAMPTZ, Default NOW())
- `updated_at` (TIMESTAMPTZ, Default NOW())

#### Table 3: `fee_policies`
Stores global fee policy and contact information (Singleton table).
- `id` (INTEGER, Primary Key) — Fixed value = 1
- `note` (TEXT) — Public fee note
- `contact_for_fees` (JSONB, NOT NULL) — Contact channels (phone, whatsapp, email)
- `general_info` (JSONB, NOT NULL) — Includes list, price range, fee discussion details, additional charges
- `created_at` (TIMESTAMPTZ, Default NOW())
- `updated_at` (TIMESTAMPTZ, Default NOW())

#### Table 4: `program_fees`
Stores per-program fee metadata.
- `id` (VARCHAR(50), Primary Key, Foreign Key -> `courses.id`) — Matches course ID
- `name` (VARCHAR(150), NOT NULL) — Program name
- `duration` (VARCHAR(50), NOT NULL) — Program duration
- `fee` (VARCHAR(50), NOT NULL) — Fee description / status
- `created_at` (TIMESTAMPTZ, Default NOW())
- `updated_at` (TIMESTAMPTZ, Default NOW())

#### Table 5: `eligibility_policies`
Stores overall admission process steps and general eligibility policy (Singleton table).
- `id` (INTEGER, Primary Key) — Fixed value = 1
- `general_policy` (TEXT, NOT NULL) — Overall eligibility policy statement
- `admission_process` (JSONB, NOT NULL) — Array of 5-step admission process objects
- `demo_class` (JSONB, NOT NULL) — Free demo details (available, cost, description)
- `created_at` (TIMESTAMPTZ, Default NOW())
- `updated_at` (TIMESTAMPTZ, Default NOW())

#### Table 6: `program_eligibility`
Stores per-program target class ranges and requirements.
- `id` (INTEGER, Primary Key, Autoincrement / Serial)
- `program_name` (VARCHAR(150), NOT NULL, Index) — Matches course/program name
- `course_id` (VARCHAR(50), Foreign Key -> `courses.id`, Nullable) — Optional reference to course ID
- `min_class` (VARCHAR(50), NOT NULL) — Minimum class requirement
- `max_class` (VARCHAR(50), NOT NULL) — Maximum class requirement
- `notes` (TEXT) — Special eligibility notes
- `created_at` (TIMESTAMPTZ, Default NOW())
- `updated_at` (TIMESTAMPTZ, Default NOW())

#### Table 7: `availability_info`
Stores general schedule and seat availability details (Singleton table).
- `id` (INTEGER, Primary Key) — Fixed value = 1
- `institute_timings` (JSONB, NOT NULL) — Operating days & opening/closing times
- `batch_timings` (JSONB, NOT NULL) — Batch schedule details
- `one_to_one_tuition` (JSONB, NOT NULL) — Flexible tuition policy
- `contact_for_current_seat_availability` (JSONB, NOT NULL) — Seat verification contacts
- `created_at` (TIMESTAMPTZ, Default NOW())
- `updated_at` (TIMESTAMPTZ, Default NOW())

#### Table 8: `admission_status`
Stores current admission cycle status (Singleton table).
- `id` (INTEGER, Primary Key) — Fixed value = 1
- `current_status` (VARCHAR(50), NOT NULL) — e.g., 'Open'
- `note` (TEXT) — Rolling admissions note
- `seat_limit_per_batch` (VARCHAR(50)) — e.g., '15-20 students'
- `batch_slots` (JSONB, NOT NULL) — Slot definitions and timings
- `free_demo` (JSONB, NOT NULL) — Demo availability info
- `contact_to_check_availability` (JSONB, NOT NULL) — Contact phone/whatsapp/email/hours
- `created_at` (TIMESTAMPTZ, Default NOW())
- `updated_at` (TIMESTAMPTZ, Default NOW())

---

## 3. Primary & Foreign Keys & Indexes
- **Primary Keys**: `courses.id`, `branches.id`, `program_fees.id`, `program_eligibility.id`, and singleton IDs for policy tables.
- **Foreign Keys**:
  - `program_fees.id` references `courses.id` (ON DELETE CASCADE)
  - `program_eligibility.course_id` references `courses.id` (ON DELETE SET NULL)
- **Indexes**:
  - `ix_courses_category` on `courses(category)`
  - `ix_program_eligibility_program_name` on `program_eligibility(program_name)`

---

## 4. Mapping JSON -> Database
- JSON Arrays containing scalar strings (e.g. `subjects`, `exams_covered`, `nearby_landmarks`) map to PostgreSQL `JSONB` columns for straightforward querying.
- Structured objects (e.g. `address`, `contact`, `timings`, `batch_slots`, `admission_process`) map directly to PostgreSQL `JSONB`.
- Fixed policy entities use single-row tables (id=1) for safe upserts and atomic updates.
- Normalized entities (`courses`, `branches`, `program_fees`, `program_eligibility`) map directly to relational tables.

---

## 5. Key Assumptions
1. All 14 programs in `fees.json` map 1:1 with `courses.json` via program `id`.
2. Program eligibility entries match courses either by explicit `program` name or mapped `course_id`.
3. Singleton policy tables hold global institutional configurations. Seeding executes via `MERGE` / `ON CONFLICT DO UPDATE` (upsert) ensuring strict idempotency.
