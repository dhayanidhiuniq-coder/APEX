-- APEX user profiles (Story 1.2 — Identity & Authentication)
--
-- Minimum storage for application profile data that is not an authentication
-- credential. Credentials live exclusively in Supabase Auth (`auth.users`) and
-- are never copied here.
--
-- HOW TO APPLY
--   1. Supabase dashboard -> SQL Editor -> New query -> paste -> Run.
--   2. Or via the CLI:  supabase db push
--
-- NOTE: APEX itself does not read or write this table yet. Nothing in Story 1.2
-- depends on it, and the app runs correctly without it. It exists so name and
-- age have a first-class, queryable home before Story 1.3 needs them, and so
-- Row Level Security is settled while the table has exactly one shape.
--
-- WHY A TRIGGER RATHER THAN A CLIENT INSERT
--   The Create Account form sends name and age to Supabase as user metadata.
--   This trigger mirrors that metadata into the table server-side, which means:
--     - no service-role key is needed anywhere,
--     - no anon-key `insert` that has to fail gracefully if this file has not
--       been applied yet,
--     - and no second place where a profile row could be forged by a client.

-- ---------------------------------------------------------------------------
-- Table
-- ---------------------------------------------------------------------------

create table if not exists public.profiles (
  -- References the Supabase Auth user. ON DELETE CASCADE means removing an
  -- auth user removes the profile, so no orphans can accumulate.
  user_id uuid primary key references auth.users (id) on delete cascade,

  name text not null,
  age smallint not null,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  -- Guards the invariants the application layer already enforces, so a bad
  -- write cannot land even if it bypasses the form.
  constraint profiles_age_range check (age between 0 and 120),
  constraint profiles_name_not_blank check (length(btrim(name)) > 0)
);

comment on table public.profiles is
  'APEX application profile. Credentials are held by Supabase Auth only.';
comment on column public.profiles.user_id is
  'Supabase Auth user id. The relationship key for all profile data.';

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------
-- The anon key is public by design, so these policies are the only thing
-- standing between a visitor and someone else's profile.

alter table public.profiles enable row level security;

-- Users may read their own profile. Reads only: a profile is created by the
-- trigger and is not user-editable, so there is deliberately no update policy.
drop policy if exists "profiles_select_own" on public.profiles;
create policy "profiles_select_own"
  on public.profiles
  for select
  to authenticated
  using (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- updated_at
-- ---------------------------------------------------------------------------

create or replace function public.set_profiles_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = public
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists profiles_set_updated_at on public.profiles;
create trigger profiles_set_updated_at
  before update on public.profiles
  for each row
  execute function public.set_profiles_updated_at();

-- ---------------------------------------------------------------------------
-- Backfill profiles from Supabase user metadata
-- ---------------------------------------------------------------------------
-- Runs on sign-up. The app writes name and age as user metadata (that is the
-- only form it ever sends them through), and this trigger copies them here.

create or replace function public.handle_new_user_profile()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  profile_name text := nullif(btrim(new.raw_user_meta_data ->> 'name'), '');
  profile_age_raw text := nullif(btrim(new.raw_user_meta_data ->> 'age'), '');
  profile_age smallint;
begin
  -- User metadata is client-supplied and arbitrary. Anything missing or
  -- malformed is skipped so a bad value can never block sign-up itself.
  if profile_name is null then
    return new;
  end if;

  begin
    profile_age := profile_age_raw::smallint;
  exception
    when others then
      return new;
  end;

  if profile_age is null or profile_age < 0 or profile_age > 120 then
    return new;
  end if;

  insert into public.profiles (user_id, name, age)
  values (new.id, profile_name, profile_age)
  on conflict (user_id) do nothing;

  return new;
end;
$$;

drop trigger if exists on_auth_user_created_profile on auth.users;
create trigger on_auth_user_created_profile
  after insert on auth.users
  for each row
  execute function public.handle_new_user_profile();