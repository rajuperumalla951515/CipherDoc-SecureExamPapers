-- ============================================================
--  CipherDoc - Full Supabase SQL Schema
--  Run this entire script in Supabase Dashboard → SQL Editor
-- ============================================================


-- ============================================================
--  1. USERS TABLE
-- ============================================================
create table if not exists public.users (
  id                text primary key,
  full_name         text not null,
  email             text not null unique,
  password_hash     text not null,
  user_type         text not null check (user_type in ('EA', 'AEF')),
  department        text,
  contact_number    text,
  is_active         boolean not null default true,
  created_at        text,

  -- EA-specific fields
  employee_id       text unique,
  designation       text,
  office_location   text,

  -- AEF-specific fields
  faculty_id        text unique,
  subject_expertise text,
  qualification     text,
  experience_years  text,
  is_authorized     boolean not null default false
);

-- Enable Row Level Security
alter table public.users enable row level security;

-- Allow the backend (anon key) full access
-- (The app handles its own auth via Flask sessions + bcrypt)
create policy "Allow full access to users table"
  on public.users
  for all
  using (true)
  with check (true);

-- Expose to Data API (grant to anon and authenticated roles)
grant select, insert, update, delete on public.users to anon, authenticated;


-- ============================================================
--  2. PAPERS TABLE
-- ============================================================
create table if not exists public.papers (
  id                      text primary key,
  exam_name               text not null,
  subject                 text not null,
  exam_date               text not null,
  exam_duration           text not null,
  total_marks             text not null,
  encrypted_questions     text not null,
  encrypted_key           text not null,
  encrypted_instructions  text not null,
  instructions_key        text not null,
  key_id                  text not null,
  created_by              text not null references public.users(id) on delete cascade,
  created_at              text,
  updated_at              text,
  status                  text not null default 'encrypted',
  is_active               boolean not null default true
);

alter table public.papers enable row level security;

create policy "Allow full access to papers table"
  on public.papers
  for all
  using (true)
  with check (true);

grant select, insert, update, delete on public.papers to anon, authenticated;


-- ============================================================
--  3. KEYS TABLE
-- ============================================================
create table if not exists public.keys (
  id          text primary key,
  key_name    text not null,
  private_key text not null,
  public_key  text not null,
  created_by  text not null references public.users(id) on delete cascade,
  created_at  text,
  is_active   boolean not null default true
);

alter table public.keys enable row level security;

create policy "Allow full access to keys table"
  on public.keys
  for all
  using (true)
  with check (true);

grant select, insert, update, delete on public.keys to anon, authenticated;


-- ============================================================
--  4. AUTHORIZATIONS TABLE
-- ============================================================
create table if not exists public.authorizations (
  id            text primary key,
  faculty_id    text not null references public.users(id) on delete cascade,
  paper_id      text not null references public.papers(id) on delete cascade,
  authorized_by text not null references public.users(id) on delete cascade,
  authorized_at text,
  is_active     boolean not null default true,
  unique (faculty_id, paper_id)   -- one authorization record per faculty-paper pair
);

alter table public.authorizations enable row level security;

create policy "Allow full access to authorizations table"
  on public.authorizations
  for all
  using (true)
  with check (true);

grant select, insert, update, delete on public.authorizations to anon, authenticated;


-- ============================================================
--  5. ACCESS LOGS TABLE
-- ============================================================
create table if not exists public.access_logs (
  id        text primary key,
  user_id   text not null references public.users(id) on delete cascade,
  user_type text not null check (user_type in ('EA', 'AEF', 'USER')),
  action    text not null,
  details   text,
  timestamp text not null
);

alter table public.access_logs enable row level security;

create policy "Allow full access to access_logs table"
  on public.access_logs
  for all
  using (true)
  with check (true);

grant select, insert, update, delete on public.access_logs to anon, authenticated;


-- ============================================================
--  6. USEFUL INDEXES FOR PERFORMANCE
-- ============================================================
create index if not exists idx_users_email        on public.users (lower(email));
create index if not exists idx_users_user_type    on public.users (user_type);
create index if not exists idx_papers_key_id      on public.papers (key_id);
create index if not exists idx_papers_created_by  on public.papers (created_by);
create index if not exists idx_auth_faculty_id    on public.authorizations (faculty_id);
create index if not exists idx_auth_paper_id      on public.authorizations (paper_id);
create index if not exists idx_logs_user_id       on public.access_logs (user_id);
create index if not exists idx_logs_timestamp     on public.access_logs (timestamp);


-- ============================================================
--  Done! All tables are ready.
-- ============================================================
