-- #25: 既存の自由コメントは「その他」として保持。主催者の調整案を下書き再提出から保護。
ALTER TABLE selection_room_comments ADD COLUMN kind VARCHAR(20) NOT NULL DEFAULT 'その他';
ALTER TABLE selection_published_proposals ADD COLUMN curated TINYINT NOT NULL DEFAULT 0;
