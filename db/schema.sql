-- Godseye user data, for Postgres. Mirrors src/lib/store/types.ts (UserRecord).
-- Not applied anywhere yet: the app runs on the local file store (src/lib/store/file.ts) until a database exists.
-- The Postgres store implements the same UserStore interface against these tables.

create table if not exists users (
  id                  text primary key,           -- the login provider's user id
  created_at          timestamptz not null default now(),
  profile             jsonb not null default '{"summary": ""}',   -- usual leg count, book, sports, running summary
  account             jsonb,                      -- bankroll, risk profile, weekly unit, user limits (src/lib/staking.ts Account)
  subscription_tier   text not null default 'none' check (subscription_tier in ('none', 'pro', 'elite')),
  subscription_status text not null default 'none' check (subscription_status in ('none', 'active', 'past_due', 'canceled')),
  current_period_end  timestamptz,
  canceled_at         timestamptz,
  archived_until      timestamptz                 -- after a cancel, history is held until this time
);

create table if not exists bets (
  id           text primary key,
  user_id      text not null references users (id) on delete cascade,
  placed_at    timestamptz not null,
  sport        text not null,
  book         text not null default '',
  legs         jsonb not null,                    -- [{ description, odds, game }]
  stake        numeric(12, 2) not null,
  status       text not null check (status in ('open', 'won', 'lost', 'push')),
  price        integer,                           -- American odds for the whole bet
  closing_odds integer,
  model_chance double precision                   -- the algorithm's chance when the bet was logged
);
create index if not exists bets_user_placed on bets (user_id, placed_at desc);

create table if not exists saved_slips (
  id       text primary key,
  user_id  text not null references users (id) on delete cascade,
  bet_id   text references bets (id) on delete set null,
  saved_at timestamptz not null,
  sport    text not null,
  built    text not null,                         -- which algorithm build the legs were rated on
  legs     jsonb not null
);

create table if not exists conversations (
  id         text primary key,
  user_id    text not null references users (id) on delete cascade,
  started_at timestamptz not null,
  updated_at timestamptz not null,
  messages   jsonb not null,                      -- the exchange as the model needs it back
  display    jsonb not null,                      -- what the user saw: lines and cards
  summarized boolean not null default false,
  archived   boolean not null default false
);
create index if not exists conversations_user_updated on conversations (user_id, updated_at desc);

create table if not exists advisor_messages (     -- one row per chat message sent, for the daily cap
  user_id text not null references users (id) on delete cascade,
  sent_at timestamptz not null
);
create index if not exists advisor_messages_user_sent on advisor_messages (user_id, sent_at desc);

create table if not exists usage (                -- one row per model call, for API cost per subscriber
  id                 bigserial primary key,
  user_id            text not null references users (id) on delete cascade,
  at                 timestamptz not null,
  model              text not null,
  purpose            text not null check (purpose in ('chat', 'summary', 'slip-read')),
  input_tokens       integer not null,
  output_tokens      integer not null,
  cache_read_tokens  integer not null default 0,
  cache_write_tokens integer not null default 0,
  cost_usd           numeric(12, 6) not null
);
create index if not exists usage_user_at on usage (user_id, at desc);
