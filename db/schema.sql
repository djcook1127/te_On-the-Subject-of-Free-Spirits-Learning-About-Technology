-- 最初のPoC：ルームと幹事の保存。既存productsは変更しない。
-- 2026-11-15のローカルPoC実行時に、許可を受けて班の開発DBへ適用済み。
-- IF NOT EXISTSは既存テーブルの列を更新しない。DROPして作り直さないこと。
CREATE TABLE IF NOT EXISTS consultations (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(100) NOT NULL,
  budget_total INT NOT NULL,
  member_count INT NOT NULL,
  concerns VARCHAR(100) NOT NULL DEFAULT '',
  deliver_by DATE NOT NULL COMMENT '受け取り期限。APIで土日祝日を拒否する',
  decide_by DATE NULL COMMENT '今回の作成APIでは扱わない',
  organizer_id INT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CHECK (budget_total >= 1),
  CHECK (member_count >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS consultation_members (
  id INT AUTO_INCREMENT PRIMARY KEY,
  consultation_id INT NOT NULL,
  nickname VARCHAR(30) NOT NULL,
  joined_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_room_nickname (consultation_id, nickname),
  FOREIGN KEY (consultation_id) REFERENCES consultations(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
