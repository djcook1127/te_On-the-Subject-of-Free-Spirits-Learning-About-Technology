-- #22-1 (#24): 既存consultations・consultation_membersは再利用する。
-- 既存テーブルのALTER・DROP、商品データの更新を行わない。
CREATE TABLE IF NOT EXISTS selection_state (
  room_id INT PRIMARY KEY,
  phase VARCHAR(20) NOT NULL DEFAULT 'collecting',
  decision JSON NULL,
  CHECK (phase IN ('collecting','voting','decided')),
  FOREIGN KEY (room_id) REFERENCES consultations(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS selection_submitters (
  room_id INT NOT NULL,
  member_id INT NOT NULL,
  submitted TINYINT NOT NULL DEFAULT 0,
  version INT NOT NULL DEFAULT 0,
  PRIMARY KEY (room_id,member_id),
  CHECK (submitted IN (0,1)), CHECK (version >= 0),
  FOREIGN KEY (room_id) REFERENCES consultations(id) ON DELETE CASCADE,
  FOREIGN KEY (member_id) REFERENCES consultation_members(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS selection_proposals (
  room_id INT NOT NULL,
  member_id INT NOT NULL,
  product_id VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  reason VARCHAR(100) NOT NULL,
  gift JSON NOT NULL,
  PRIMARY KEY (room_id,member_id,product_id),
  FOREIGN KEY (room_id,member_id) REFERENCES selection_submitters(room_id,member_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS selection_notes (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  room_id INT NOT NULL,
  member_id INT NOT NULL,
  kind VARCHAR(30) NOT NULL,
  text VARCHAR(300) NOT NULL,
  INDEX (room_id,id),
  FOREIGN KEY (room_id) REFERENCES consultations(id) ON DELETE CASCADE,
  FOREIGN KEY (member_id) REFERENCES consultation_members(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS selection_votes (
  room_id INT NOT NULL,
  member_id INT NOT NULL,
  product_id VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  stars TINYINT NOT NULL,
  PRIMARY KEY (room_id,member_id,product_id),
  INDEX (room_id,product_id),
  CHECK (stars BETWEEN 1 AND 3),
  FOREIGN KEY (room_id) REFERENCES consultations(id) ON DELETE CASCADE,
  FOREIGN KEY (member_id) REFERENCES consultation_members(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS selection_comments (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  room_id INT NOT NULL,
  member_id INT NOT NULL,
  product_id VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  text VARCHAR(300) NOT NULL,
  INDEX (room_id,product_id,id),
  FOREIGN KEY (room_id) REFERENCES consultations(id) ON DELETE CASCADE,
  FOREIGN KEY (member_id) REFERENCES consultation_members(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS consultation_member_sessions (
  token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
  room_id INT NOT NULL,
  member_id INT NOT NULL,
  expires_at BIGINT NOT NULL,
  legacy_room_id INT NULL,
  INDEX (room_id,member_id), INDEX (expires_at),
  FOREIGN KEY (room_id) REFERENCES consultations(id) ON DELETE CASCADE,
  FOREIGN KEY (member_id) REFERENCES consultation_members(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS selection_imports (
  source_key CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  old_room_id INT NOT NULL,
  new_room_id INT NOT NULL,
  member_map JSON NOT NULL,
  imported_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (source_key,old_room_id),
  UNIQUE KEY (new_room_id),
  FOREIGN KEY (new_room_id) REFERENCES consultations(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
