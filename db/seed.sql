-- 데모 방 (/r/demo). 실행할 때마다 지우고 다시 넣는다.
-- 10/3 회의안: 발표자 계좌 1 + 3명(이름 · 총액만) + 중도포기 1
-- 기간은 가짜 은행 거래 날짜(app/expenses/mockbank/data.py 의 START_DATE, 10/2 ~ 10/8)에 맞춘다.
-- 결과 카드에서 보이는 것: 짠돌이(1등) · 발표자(조정 후 2등 정도) · 카페중독 · 큰손(초과, 미확인) · 포기각(항복)

-- Supabase SQL Editor 에서 바로 실행해도 한국 날짜로 계산되게 한다 (기본은 UTC)
set timezone to 'Asia/Seoul';

delete from rooms where code = 'demo';   -- 멤버와 지출도 같이 지워진다

insert into rooms (code, name, start_date, end_date)
values ('demo', '데모 방', date '2026-10-02', date '2026-10-08');

-- 발표자: 가짜 은행 계좌 A 를 연결한 상태. 지출은 시연 때 불러온다 (아직 조정 전이라 미확인)
-- 나머지: 시연용이라 계좌 없이 총액만 넣는다
insert into members (room_code, nickname, budget, fintech_use_num, confirmed_at, gave_up_at) values
    ('demo', '발표자',   100000, 'BTG00000000000000000000A', null,                                null),
    ('demo', '짠돌이',   100000, null, timestamptz '2026-10-07 21:00+09', null),
    ('demo', '카페중독',  80000, null, timestamptz '2026-10-07 22:30+09', null),
    ('demo', '큰손',      70000, null, null,                                null),
    ('demo', '포기각',    50000, null, null,                                timestamptz '2026-10-04 23:00+09');

-- 총액만 있는 멤버: 합계 한 줄씩. 결과 카드에는 총액만 보이고 상세는 보이지 않는다
--   짠돌이 22,000 / 100,000 = 22%  · 카페중독 52,000 / 80,000 = 65%
--   큰손   85,000 /  70,000 = 121% (초과)  · 포기각 61,000 (항복이라 금액 숨김)
insert into expenses (member_id, spent_on, merchant, amount, people, excluded, source, ref)
select m.id, e.spent_on, '시연용 합계', e.amount, 1, false, 'manual', null
from members m
join (values
    ('짠돌이',   date '2026-10-07', 22000),
    ('카페중독', date '2026-10-07', 52000),
    ('큰손',     date '2026-10-07', 85000),
    ('포기각',   date '2026-10-04', 61000)
) as e(nickname, spent_on, amount) on e.nickname = m.nickname
where m.room_code = 'demo';
