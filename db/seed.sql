-- 데모 방 (/r/demo). 실행할 때마다 지우고 다시 넣는다.
-- 날짜는 실행한 날 기준이라 오늘이 항상 기간 안에 들어간다 (시작 3일 전 ~ 4일 뒤, 7일).
-- 보드에서 보이는 것: 절약왕(여유) · 큰손(초과) · 늦잠(미제출, 지출 없음)

delete from rooms where code = 'demo';   -- 멤버와 지출도 같이 지워진다

insert into rooms (code, name, start_date, end_date, upload_cycle, deadline_weekday)
values ('demo', '데모 방', current_date - 3, current_date + 4, 7, 6);

insert into members (room_code, nickname, budget) values
    ('demo', '절약왕', 100000),
    ('demo', '큰손',    70000),
    ('demo', '늦잠',    50000);

-- 절약왕: 내 몫 합계 22,000원 (예산 100,000원)
insert into expenses (member_id, spent_on, merchant, amount, people, excluded, source, ref)
select m.id, current_date - e.days_ago, e.merchant, e.amount, e.people, e.excluded, e.source, e.ref
from members m
join (values
    (3, '학생식당',     5000,  1, false, 'virtual', 'demo-a-001'),
    (2, '편의점',       3500,  1, false, 'virtual', 'demo-a-002'),
    (1, '고깃집',      36000,  3, false, 'virtual', 'demo-a-003'),
    (0, '통신비',      45000,  1, true,  'virtual', 'demo-a-004'),
    (0, '문구점',       1500,  1, false, 'manual',  null)
) as e(days_ago, merchant, amount, people, excluded, source, ref) on true
where m.room_code = 'demo' and m.nickname = '절약왕';

-- 큰손: 내 몫 합계 85,000원 (예산 70,000원 → 초과)
insert into expenses (member_id, spent_on, merchant, amount, people, excluded, source, ref)
select m.id, current_date - e.days_ago, e.merchant, e.amount, e.people, e.excluded, e.source, e.ref
from members m
join (values
    (3, '카페',         6500,  1, false, 'virtual', 'demo-b-001'),
    (2, '택시',        18500,  1, false, 'virtual', 'demo-b-002'),
    (2, '옷가게',      49000,  1, false, 'virtual', 'demo-b-003'),
    (1, '치킨',        22000,  2, false, 'virtual', 'demo-b-004'),
    (0, '월세',       400000,  1, true,  'virtual', 'demo-b-005')
) as e(days_ago, merchant, amount, people, excluded, source, ref) on true
where m.room_code = 'demo' and m.nickname = '큰손';

-- 늦잠: 지출 없음 (미제출)
