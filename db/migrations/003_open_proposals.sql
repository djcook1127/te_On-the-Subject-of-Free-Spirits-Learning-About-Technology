-- #22-2 (#25): 公開済み候補と下書きを分け、全体10品をAPIのルームロックで制御する。
CREATE TABLE IF NOT EXISTS selection_published_proposals (
  room_id INT NOT NULL,
  member_id INT NOT NULL,
  product_id VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  reason VARCHAR(100) NOT NULL,
  gift JSON NOT NULL,
  PRIMARY KEY (room_id,member_id,product_id),
  FOREIGN KEY (room_id,member_id) REFERENCES selection_submitters(room_id,member_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS selection_room_comments (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  room_id INT NOT NULL,
  member_id INT NOT NULL,
  text VARCHAR(300) NOT NULL,
  INDEX (room_id,id),
  FOREIGN KEY (room_id) REFERENCES consultations(id) ON DELETE CASCADE,
  FOREIGN KEY (member_id) REFERENCES consultation_members(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 旧仕様で提出済みの候補を保持。再適用で既存の公開内容を上書きしない。
INSERT INTO selection_published_proposals(room_id,member_id,product_id,reason,gift)
  SELECT p.room_id,p.member_id,p.product_id,p.reason,p.gift FROM selection_proposals p
  JOIN selection_submitters s ON s.room_id=p.room_id AND s.member_id=p.member_id
  WHERE s.submitted=1
  ON DUPLICATE KEY UPDATE product_id=VALUES(product_id);
