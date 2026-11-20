-- 既存ルームの参加者を閉じ込めない。新規ルームのみAPIから0で初期化する。
ALTER TABLE selection_state ADD COLUMN organizer_submitted TINYINT NOT NULL DEFAULT 1;
