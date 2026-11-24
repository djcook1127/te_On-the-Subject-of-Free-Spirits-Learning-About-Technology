-- 1ルームに有効な招待リンクは最大1つ。元のトークンは保存しない。
CREATE TABLE IF NOT EXISTS consultation_invites (
  room_id INT PRIMARY KEY,
  token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  expires_at BIGINT NOT NULL,
  FOREIGN KEY (room_id) REFERENCES consultations(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
