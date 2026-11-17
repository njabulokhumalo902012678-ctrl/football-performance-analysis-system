-- MySQL / MariaDB schema generated from app/schema.sql
-- NOTE: generated mechanically and NOT executed against a MySQL server by the original author.
-- Review, load into a test database first and run the checks in docs/DEPLOYMENT.md.
SET FOREIGN_KEY_CHECKS=1;

-- Football Data and Performance Analysis Company - database schema
-- Portable SQL: runs on SQLite (default) and is converted to MySQL/MariaDB by tools/make_mysql_schema.py
-- Timestamps are stored as 'YYYY-MM-DD HH:MM:SS' values.

CREATE TABLE settings (
  skey VARCHAR(80) PRIMARY KEY,
  svalue TEXT,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ===================== USERS AND SECURITY =====================
CREATE TABLE roles (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(40) NOT NULL UNIQUE,
  name VARCHAR(120) NOT NULL,
  description TEXT,
  dashboard_title VARCHAR(120),
  is_primary INT NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE permissions (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(60) NOT NULL UNIQUE,
  description VARCHAR(255)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE role_permissions (
  role_id INT NOT NULL,
  permission_id INT NOT NULL,
  PRIMARY KEY (role_id, permission_id),
  FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
  FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE users (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(60) NOT NULL UNIQUE,
  email VARCHAR(190) NOT NULL UNIQUE,
  full_name VARCHAR(150) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  user_type VARCHAR(20) NOT NULL DEFAULT 'employee',
  is_active INT NOT NULL DEFAULT 1,
  failed_logins INT NOT NULL DEFAULT 0,
  locked_until DATETIME,
  last_login_at DATETIME,
  must_change_password INT NOT NULL DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE user_roles (
  user_id INT NOT NULL,
  role_id INT NOT NULL,
  PRIMARY KEY (user_id, role_id),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE password_resets (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  token_hash VARCHAR(128) NOT NULL,
  expires_at DATETIME NOT NULL,
  used_at DATETIME,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE audit_logs (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  user_id INT,
  action VARCHAR(80) NOT NULL,
  entity VARCHAR(60),
  entity_id INT,
  details TEXT,
  ip_address VARCHAR(64),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX idx_audit_entity ON audit_logs(entity, entity_id);
CREATE INDEX idx_audit_created ON audit_logs(created_at);
CREATE TABLE error_logs (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  user_id INT,
  path VARCHAR(255),
  message TEXT,
  trace TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ===================== CLIENTS AND COMMERCIAL =====================
CREATE TABLE clients (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  client_type VARCHAR(40) NOT NULL,
  name VARCHAR(190) NOT NULL,
  contact_person VARCHAR(150),
  email VARCHAR(190),
  phone VARCHAR(50),
  services_requested TEXT,
  agreement_status VARCHAR(30) NOT NULL DEFAULT 'prospect',
  assigned_user_id INT,
  next_followup DATE,
  notes TEXT,
  is_active INT NOT NULL DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (assigned_user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE client_users (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  client_id INT NOT NULL,
  user_id INT NOT NULL UNIQUE,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE leads (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(190) NOT NULL,
  org_type VARCHAR(40),
  contact_person VARCHAR(150),
  email VARCHAR(190),
  phone VARCHAR(50),
  status VARCHAR(30) NOT NULL DEFAULT 'new',
  source VARCHAR(80),
  assigned_user_id INT,
  next_followup DATE,
  notes TEXT,
  converted_client_id INT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (assigned_user_id) REFERENCES users(id) ON DELETE SET NULL,
  FOREIGN KEY (converted_client_id) REFERENCES clients(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE contact_history (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  lead_id INT,
  client_id INT,
  contact_date DATE NOT NULL,
  channel VARCHAR(40),
  summary TEXT NOT NULL,
  user_id INT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE,
  FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE marketing_campaigns (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(190) NOT NULL,
  channel VARCHAR(60),
  start_date DATE,
  end_date DATE,
  budget DOUBLE,
  link VARCHAR(255),
  status VARCHAR(30) NOT NULL DEFAULT 'planned',
  results TEXT,
  notes TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE services (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(190) NOT NULL,
  description TEXT,
  unit_price DOUBLE NOT NULL DEFAULT 0,
  is_active INT NOT NULL DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE proposals (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  client_id INT,
  lead_id INT,
  title VARCHAR(190) NOT NULL,
  service_id INT,
  amount DOUBLE NOT NULL DEFAULT 0,
  status VARCHAR(30) NOT NULL DEFAULT 'draft',
  valid_until DATE,
  notes TEXT,
  created_by INT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL,
  FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE SET NULL,
  FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE SET NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE invoices (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  invoice_number VARCHAR(40) NOT NULL UNIQUE,
  client_id INT NOT NULL,
  proposal_id INT,
  issue_date DATE NOT NULL,
  due_date DATE NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'draft',
  subtotal DOUBLE NOT NULL DEFAULT 0,
  tax_rate DOUBLE NOT NULL DEFAULT 0,
  tax_amount DOUBLE NOT NULL DEFAULT 0,
  total DOUBLE NOT NULL DEFAULT 0,
  notes TEXT,
  created_by INT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (client_id) REFERENCES clients(id),
  FOREIGN KEY (proposal_id) REFERENCES proposals(id) ON DELETE SET NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX idx_invoices_client ON invoices(client_id);
CREATE INDEX idx_invoices_status ON invoices(status);
CREATE TABLE invoice_items (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  invoice_id INT NOT NULL,
  service_id INT,
  description VARCHAR(255) NOT NULL,
  quantity DOUBLE NOT NULL DEFAULT 1,
  unit_price DOUBLE NOT NULL DEFAULT 0,
  line_total DOUBLE NOT NULL DEFAULT 0,
  FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
  FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE payments (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  invoice_id INT NOT NULL,
  paid_date DATE NOT NULL,
  amount DOUBLE NOT NULL,
  method VARCHAR(40),
  reference VARCHAR(120),
  recorded_by INT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
  FOREIGN KEY (recorded_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE client_requests (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  client_id INT NOT NULL,
  user_id INT,
  kind VARCHAR(20) NOT NULL DEFAULT 'request',
  subject VARCHAR(190) NOT NULL,
  message TEXT NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'open',
  response TEXT,
  responded_by INT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
  FOREIGN KEY (responded_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ===================== FOOTBALL RECORDS =====================
CREATE TABLE clubs (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(190) NOT NULL UNIQUE,
  country VARCHAR(100),
  contact_details TEXT,
  category VARCHAR(60),
  verification_status VARCHAR(30) NOT NULL DEFAULT 'unverified',
  notes TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE teams (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  club_id INT,
  name VARCHAR(190) NOT NULL,
  competition_category VARCHAR(80),
  age_gender_category VARCHAR(60),
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  notes TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (club_id) REFERENCES clubs(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE players (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  full_name VARCHAR(190) NOT NULL,
  date_of_birth DATE,
  dob_authorised INT NOT NULL DEFAULT 0,
  position VARCHAR(40),
  preferred_foot VARCHAR(20),
  foot_verified INT NOT NULL DEFAULT 0,
  current_team_id INT,
  shirt_number INT,
  nationality VARCHAR(80),
  profile_image VARCHAR(255),
  image_permitted INT NOT NULL DEFAULT 0,
  verification_status VARCHAR(30) NOT NULL DEFAULT 'unverified',
  profile_source VARCHAR(190),
  date_last_verified DATE,
  notes TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (current_team_id) REFERENCES teams(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX idx_players_team ON players(current_team_id);
CREATE TABLE player_team_history (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  player_id INT NOT NULL,
  team_id INT NOT NULL,
  start_date DATE,
  end_date DATE,
  shirt_number INT,
  notes TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE,
  FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE competitions (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(190) NOT NULL,
  organising_body VARCHAR(190),
  category VARCHAR(80),
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  notes TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE seasons (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  competition_id INT NOT NULL,
  name VARCHAR(60) NOT NULL,
  start_date DATE,
  end_date DATE,
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (competition_id) REFERENCES competitions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE competition_teams (
  season_id INT NOT NULL,
  team_id INT NOT NULL,
  PRIMARY KEY (season_id, team_id),
  FOREIGN KEY (season_id) REFERENCES seasons(id) ON DELETE CASCADE,
  FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE venues (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(190) NOT NULL,
  region VARCHAR(100),
  pitch_details TEXT,
  notes TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE data_sources (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(190) NOT NULL,
  source_type VARCHAR(40) NOT NULL DEFAULT 'live_collection',
  permission_status VARCHAR(30) NOT NULL DEFAULT 'own_collection',
  licence_notes TEXT,
  url VARCHAR(255),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE matches (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  match_code VARCHAR(40) NOT NULL UNIQUE,
  competition_id INT,
  season_id INT,
  home_team_id INT NOT NULL,
  away_team_id INT NOT NULL,
  kickoff DATETIME NOT NULL,
  venue_id INT,
  status VARCHAR(30) NOT NULL DEFAULT 'scheduled',
  duration_minutes INT NOT NULL DEFAULT 90,
  home_score INT,
  away_score INT,
  score_source VARCHAR(190),
  possession_home DOUBLE,
  possession_away DOUBLE,
  possession_source VARCHAR(190),
  attendance INT,
  collection_deadline DATETIME,
  client_id INT,
  notes TEXT,
  created_by INT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (competition_id) REFERENCES competitions(id) ON DELETE SET NULL,
  FOREIGN KEY (season_id) REFERENCES seasons(id) ON DELETE SET NULL,
  FOREIGN KEY (home_team_id) REFERENCES teams(id),
  FOREIGN KEY (away_team_id) REFERENCES teams(id),
  FOREIGN KEY (venue_id) REFERENCES venues(id) ON DELETE SET NULL,
  FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX idx_matches_status ON matches(status);
CREATE INDEX idx_matches_kickoff ON matches(kickoff);
CREATE TABLE match_status_history (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  match_id INT NOT NULL,
  old_status VARCHAR(30),
  new_status VARCHAR(30) NOT NULL,
  user_id INT,
  note VARCHAR(255),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE match_checklist_items (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  match_id INT NOT NULL,
  label VARCHAR(190) NOT NULL,
  done INT NOT NULL DEFAULT 0,
  done_by INT,
  done_at DATETIME,
  FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
  FOREIGN KEY (done_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE collection_assignments (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  match_id INT NOT NULL,
  user_id INT NOT NULL,
  assignment_role VARCHAR(30) NOT NULL,
  deadline DATETIME,
  priority VARCHAR(20) NOT NULL DEFAULT 'normal',
  status VARCHAR(20) NOT NULL DEFAULT 'assigned',
  notes VARCHAR(255),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (match_id, user_id, assignment_role),
  FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE match_collection_scope (
  match_id INT NOT NULL,
  category VARCHAR(30) NOT NULL,
  collected INT NOT NULL DEFAULT 0,
  PRIMARY KEY (match_id, category),
  FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE match_squads (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  match_id INT NOT NULL,
  team_id INT NOT NULL,
  player_id INT NOT NULL,
  shirt_number INT,
  is_starter INT NOT NULL DEFAULT 0,
  position VARCHAR(40),
  UNIQUE (match_id, player_id),
  FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
  FOREIGN KEY (team_id) REFERENCES teams(id),
  FOREIGN KEY (player_id) REFERENCES players(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE appearances (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  match_id INT NOT NULL,
  team_id INT NOT NULL,
  player_id INT NOT NULL,
  role VARCHAR(20) NOT NULL DEFAULT 'starter',
  start_position VARCHAR(40),
  sub_on_minute INT,
  sub_off_minute INT,
  dismissed_minute INT,
  appearance_status VARCHAR(20) NOT NULL DEFAULT 'played',
  minutes_uncertain INT NOT NULL DEFAULT 0,
  source_id INT,
  verification_status VARCHAR(20) NOT NULL DEFAULT 'unverified',
  UNIQUE (match_id, player_id),
  FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
  FOREIGN KEY (team_id) REFERENCES teams(id),
  FOREIGN KEY (player_id) REFERENCES players(id),
  FOREIGN KEY (source_id) REFERENCES data_sources(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ===================== DATA COLLECTION =====================
CREATE TABLE event_types (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(40) NOT NULL UNIQUE,
  name VARCHAR(80) NOT NULL,
  category VARCHAR(30) NOT NULL,
  scope_category VARCHAR(30) NOT NULL,
  outcomes VARCHAR(255),
  needs_player INT NOT NULL DEFAULT 1,
  related_label VARCHAR(60),
  uses_coords VARCHAR(10) NOT NULL DEFAULT 'none',
  uses_set_piece INT NOT NULL DEFAULT 0,
  sort_order INT NOT NULL DEFAULT 100,
  is_active INT NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE match_events (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  match_id INT NOT NULL,
  team_id INT NOT NULL,
  player_id INT,
  event_type_id INT NOT NULL,
  period VARCHAR(10) NOT NULL DEFAULT '1H',
  minute INT,
  second INT,
  outcome VARCHAR(40),
  related_player_id INT,
  x_start DOUBLE,
  y_start DOUBLE,
  x_end DOUBLE,
  y_end DOUBLE,
  set_piece_type VARCHAR(30),
  video_timestamp INT,
  collector_id INT,
  source_id INT,
  notes TEXT,
  validation_status VARCHAR(20) NOT NULL DEFAULT 'draft',
  correction_reason VARCHAR(255),
  modified_by INT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
  FOREIGN KEY (team_id) REFERENCES teams(id),
  FOREIGN KEY (player_id) REFERENCES players(id),
  FOREIGN KEY (event_type_id) REFERENCES event_types(id),
  FOREIGN KEY (related_player_id) REFERENCES players(id),
  FOREIGN KEY (collector_id) REFERENCES users(id) ON DELETE SET NULL,
  FOREIGN KEY (source_id) REFERENCES data_sources(id) ON DELETE SET NULL,
  FOREIGN KEY (modified_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX idx_events_match ON match_events(match_id, event_type_id);
CREATE INDEX idx_events_player ON match_events(player_id);
CREATE TABLE validation_issues (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  match_id INT NOT NULL,
  event_id INT,
  issue_type VARCHAR(40) NOT NULL,
  severity VARCHAR(10) NOT NULL DEFAULT 'error',
  message VARCHAR(255) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'open',
  raised_by INT,
  resolved_by INT,
  resolved_at DATETIME,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
  FOREIGN KEY (event_id) REFERENCES match_events(id) ON DELETE SET NULL,
  FOREIGN KEY (raised_by) REFERENCES users(id) ON DELETE SET NULL,
  FOREIGN KEY (resolved_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE import_jobs (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  job_type VARCHAR(40) NOT NULL,
  filename VARCHAR(255),
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  rows_total INT NOT NULL DEFAULT 0,
  rows_ok INT NOT NULL DEFAULT 0,
  rows_failed INT NOT NULL DEFAULT 0,
  errors TEXT,
  user_id INT,
  match_id INT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
  FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ===================== ANALYSIS AND SCOUTING =====================
CREATE TABLE metric_definitions (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(40) NOT NULL UNIQUE,
  name VARCHAR(120) NOT NULL,
  subject_scope VARCHAR(20) NOT NULL,
  scope_category VARCHAR(30),
  unit VARCHAR(20),
  formula TEXT NOT NULL,
  definition TEXT,
  test_example TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE analysis_runs (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  match_id INT NOT NULL,
  run_by INT,
  data_status VARCHAR(20) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'complete',
  notes VARCHAR(255),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
  FOREIGN KEY (run_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE metric_values (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  analysis_run_id INT NOT NULL,
  subject_type VARCHAR(10) NOT NULL,
  subject_id INT NOT NULL,
  metric_code VARCHAR(40) NOT NULL,
  value DOUBLE,
  status VARCHAR(20) NOT NULL,
  note VARCHAR(255),
  basis_matches INT,
  of_matches INT,
  FOREIGN KEY (analysis_run_id) REFERENCES analysis_runs(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX idx_metric_run ON metric_values(analysis_run_id, subject_type, subject_id);
CREATE TABLE analyst_notes (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  match_id INT,
  player_id INT,
  team_id INT,
  author_id INT,
  note_type VARCHAR(30) NOT NULL,
  body TEXT NOT NULL,
  is_fact INT NOT NULL DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
  FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE SET NULL,
  FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE SET NULL,
  FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE video_assets (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(190) NOT NULL,
  match_id INT,
  reference VARCHAR(255),
  file_path VARCHAR(255),
  permission_status VARCHAR(20) NOT NULL DEFAULT 'pending',
  licence_notes TEXT,
  access_restriction VARCHAR(30) NOT NULL DEFAULT 'internal_only',
  uploaded_by INT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE SET NULL,
  FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE video_clips (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  video_id INT NOT NULL,
  match_id INT,
  player_id INT,
  start_seconds INT NOT NULL,
  end_seconds INT,
  event_category VARCHAR(40),
  tags VARCHAR(255),
  notes TEXT,
  created_by INT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (video_id) REFERENCES video_assets(id) ON DELETE CASCADE,
  FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE SET NULL,
  FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE SET NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE scouting_reports (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  player_id INT NOT NULL,
  position_role VARCHAR(60),
  observation_date DATE,
  factual_evidence TEXT,
  technical_strengths TEXT,
  tactical_strengths TEXT,
  development_areas TEXT,
  decision_making TEXT,
  video_refs TEXT,
  confidence VARCHAR(20) NOT NULL DEFAULT 'low',
  recommendation TEXT,
  analyst_id INT,
  review_status VARCHAR(20) NOT NULL DEFAULT 'draft',
  reviewer_id INT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (player_id) REFERENCES players(id),
  FOREIGN KEY (analyst_id) REFERENCES users(id) ON DELETE SET NULL,
  FOREIGN KEY (reviewer_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE scouting_report_matches (
  scouting_id INT NOT NULL,
  match_id INT NOT NULL,
  PRIMARY KEY (scouting_id, match_id),
  FOREIGN KEY (scouting_id) REFERENCES scouting_reports(id) ON DELETE CASCADE,
  FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ===================== REPORTS AND WORKFLOW =====================
CREATE TABLE reports (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  report_type VARCHAR(20) NOT NULL,
  title VARCHAR(190) NOT NULL,
  match_id INT,
  player_id INT,
  team_id INT,
  scouting_id INT,
  client_id INT,
  status VARCHAR(20) NOT NULL DEFAULT 'draft',
  data_status VARCHAR(20) NOT NULL DEFAULT 'validated',
  current_version INT NOT NULL DEFAULT 0,
  content TEXT,
  created_by INT,
  reviewer_id INT,
  review_note TEXT,
  approved_at DATETIME,
  delivered_at DATETIME,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE SET NULL,
  FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE SET NULL,
  FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE SET NULL,
  FOREIGN KEY (scouting_id) REFERENCES scouting_reports(id) ON DELETE SET NULL,
  FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
  FOREIGN KEY (reviewer_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX idx_reports_status ON reports(status);
CREATE TABLE report_versions (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  report_id INT NOT NULL,
  version INT NOT NULL,
  content TEXT NOT NULL,
  pdf_path VARCHAR(255),
  analysis_run_id INT,
  created_by INT,
  note VARCHAR(255),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (report_id, version),
  FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE,
  FOREIGN KEY (analysis_run_id) REFERENCES analysis_runs(id) ON DELETE SET NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE report_shares (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  report_id INT NOT NULL,
  client_id INT NOT NULL,
  version INT NOT NULL,
  shared_by INT,
  shared_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  status VARCHAR(20) NOT NULL DEFAULT 'delivered',
  viewed_at DATETIME,
  downloaded_at DATETIME,
  FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE,
  FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
  FOREIGN KEY (shared_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE tasks (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(190) NOT NULL,
  description TEXT,
  assigned_to INT,
  department VARCHAR(40),
  priority VARCHAR(20) NOT NULL DEFAULT 'normal',
  due_date DATE,
  status VARCHAR(20) NOT NULL DEFAULT 'open',
  related_type VARCHAR(20),
  related_id INT,
  notes TEXT,
  created_by INT,
  completed_at DATETIME,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (assigned_to) REFERENCES users(id) ON DELETE SET NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX idx_tasks_assignee ON tasks(assigned_to, status);
CREATE TABLE expenses (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  expense_date DATE NOT NULL,
  category VARCHAR(60) NOT NULL,
  description VARCHAR(255) NOT NULL,
  amount DOUBLE NOT NULL,
  payee VARCHAR(150),
  receipt_ref VARCHAR(190),
  related_match_id INT,
  related_client_id INT,
  recorded_by INT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (related_match_id) REFERENCES matches(id) ON DELETE SET NULL,
  FOREIGN KEY (related_client_id) REFERENCES clients(id) ON DELETE SET NULL,
  FOREIGN KEY (recorded_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE backup_logs (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  action VARCHAR(30) NOT NULL,
  file_path VARCHAR(255),
  size_bytes INT,
  status VARCHAR(20) NOT NULL,
  message VARCHAR(255),
  user_id INT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

