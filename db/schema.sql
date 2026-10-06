-- 버티기 테이블. 칸은 docs/BUILD_ORDER.md 의 "테이블"을 따른다.
-- 여러 번 실행해도 안전하다 (이미 있으면 건너뛴다).

create table if not exists rooms (
    code             text primary key,                 -- 링크에 들어가는 방 코드 (/r/{code})
    name             text not null,
    start_date       date not null,
    end_date         date not null,
    upload_cycle     integer not null default 7,       -- 업로드 주기(일). 기본 주 1회
    deadline_weekday smallint not null default 6,      -- 마감 요일. 0=월 ... 6=일 (파이썬 weekday())
    created_at       timestamptz not null default now(),
    check (end_date >= start_date),
    check (upload_cycle > 0),
    check (deadline_weekday between 0 and 6)
);

create table if not exists members (
    id         bigint generated always as identity primary key,
    room_code  text not null references rooms(code) on delete cascade,
    nickname   text not null,
    budget     integer not null check (budget > 0),    -- 원 단위
    created_at timestamptz not null default now()
);

create index if not exists members_room_code_idx on members(room_code);

-- 10/3 회의: 미제출을 없애고 미확인 · 항복을 둔다.
-- 이미 만든 DB 에도 칸이 붙도록 alter 로 쓴다.
alter table members add column if not exists fintech_use_num text;        -- 참여할 때 고른 가짜 은행 계좌 번호 (오픈뱅킹 명세 이름)
alter table members add column if not exists confirmed_at    timestamptz; -- 항목 조정(1/N · 제외)을 마친 시각. null = 미확인
alter table members add column if not exists gave_up_at      timestamptz; -- 항복한 시각. null = 진행 중. 먼저 포기한 사람이 맨 아래

-- 10/4: 다른 브라우저에서 링크를 열어도 닉네임 + 숫자 4자리로 다시 들어온다 (로그인 아님, 방 안에서만)
alter table members add column if not exists pin_hash text;  -- 4자리의 해시 (app/rooms/pin.py). null = 다시 들어오기 불가 (데모 멤버)

create table if not exists expenses (
    id         bigint generated always as identity primary key,
    member_id  bigint not null references members(id) on delete cascade,
    spent_on   date not null,
    merchant   text not null,
    amount     integer not null check (amount > 0),    -- 결제한 전체 금액(원). 내 몫 = amount / people
    people     smallint not null default 1 check (people >= 1),
    excluded   boolean not null default false,
    source     text not null check (source in ('virtual', 'manual', 'file')),
    ref        text check (ref <> ''),                 -- 가상 거래의 고유 번호. 직접 입력은 null
    category   text,                                   -- 비워 둔다 (10/8 이후)
    created_at timestamptz not null default now(),
    -- 같은 멤버가 같은 ref 를 두 번 저장하지 못한다. ref 가 null 이면 여러 건 가능하다.
    unique (member_id, ref)
);

create index if not exists expenses_member_id_idx on expenses(member_id);
