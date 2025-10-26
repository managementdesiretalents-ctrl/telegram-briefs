-- 1) ensure the messages table exists
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY,
  peer_id TEXT,
  msg_id TEXT,
  ts_utc TEXT,          -- store as ISO8601 UTC string
  from_me INTEGER,      -- 1 = YOU, 0 = THEM
  text TEXT,
  message_id TEXT
);

-- 2) a few synthetic rows:
-- recent conversation mentioning call/video and tasks
INSERT INTO messages(peer_id, msg_id, ts_utc, from_me, text, message_id) VALUES
('peerA','m1', datetime('now','-3 days'), 0, 'Can we schedule a video call to review budget and timeline?', 'msg-001'),
('peerA','m2', datetime('now','-2 days'), 1, 'Sure, video call is fine. We need to confirm the budget increase.', 'msg-002'),
('peerA','m3', datetime('now','-36 hours'), 0, 'Action item: send ETA for the dashboard. Deadline is Friday.', 'msg-003'),
('peerA','m4', datetime('now','-12 hours'), 1, 'ETA Thursday EOD, and cost impact is minimal.', 'msg-004');

-- an older message (>60 days) to trigger the "(from <date>)" note
INSERT INTO messages(peer_id, msg_id, ts_utc, from_me, text, message_id) VALUES
('peerA','m_old', datetime('now','-75 days'), 0, 'Old note: original deadline was tentative.', 'msg-005');
