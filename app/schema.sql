-- Football Data and Performance Analysis Company - database schema
-- Portable SQL: runs on SQLite (default) and is converted to MySQL/MariaDB by tools/make_mysql_schema.py
-- Timestamps are stored as 'YYYY-MM-DD HH:MM:SS' values.

CREATE TABLE settings (
  skey VARCHAR(80) PRIMARY KEY,
  svalue TEXT,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ===================== USERS AND SECURITY =====================
CREATE TABLE roles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code VARCHAR(40) NOT NULL UNIQUE,
  name VARCHAR(120) NOT NULL,
  description TEXT,
  dashboard_title VARCHAR(120),
  is_primary INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE permissions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code VARCHAR(60) NOT NULL UNIQUE,
  description VARCHAR(255)
);
CREATE TABLE role_permissions (
  role_id INTEGER NOT NULL,
  permission_id INTEGER NOT NULL,
  PRIMARY KEY (role_id, permission_id),
  FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
  FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
);
CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username VARCHAR(60) NOT NULL UNIQUE,
  email VARCHAR(190) NOT NULL UNIQUE,
  full_name VARCHAR(150) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  user_type VARCHAR(20) NOT NULL DEFAULT 'employee',
  is_active INTEGER NOT NULL DEFAULT 1,
  failed_logins INTEGER NOT NULL DEFAULT 0,
  locked_until DATETIME,
  last_login_at DATETIME,
  must_change_password INTEGER NOT NULL DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE user_roles (
  user_id INTEGER NOT NULL,
  role_id INTEGER NOT NULL,
  PRIMARY KEY (user_id, role_id),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
);
CREATE TABLE password_resets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  token_hash VARCHAR(128) NOT NULL,
  expires_at DATETIME NOT NULL,
  used_at DATETIME,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE audit_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  action VARCHAR(80) NOT NULL,
  entity VARCHAR(60),
  entity_id INTEGER,
  details TEXT,
  ip_address VARCHAR(64),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX idx_audit_entity ON audit_logs(entity, entity_id);
CREATE INDEX idx_audit_created ON audit_logs(created_at);
CREATE TABLE error_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  path VARCHAR(255),
  message TEXT,
  trace TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ===================== CLIENTS AND COMMERCIAL =====================
CREATE TABLE clients (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_type VARCHAR(40) NOT NULL,
  name VARCHAR(190) NOT NULL,
  contact_person VARCHAR(150),
  email VARCHAR(190),
  phone VARCHAR(50),
  services_requested TEXT,
  agreement_status VARCHAR(30) NOT NULL DEFAULT 'prospect',
  assigned_user_id INTEGER,
  next_followup DATE,
  notes TEXT,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (assigned_user_id) REFERENCES users(id) ON DELETE SET NULL
);
CREATE TABLE client_users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL UNIQUE,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE leads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name VARCHAR(190) NOT NULL,
  org_type VARCHAR(40),
  contact_person VARCHAR(150),
  email VARCHAR(190),
  phone VARCHAR(50),
  status VARCHAR(30) NOT NULL DEFAULT 'new',
  source VARCHAR(80),
  assigned_user_id INTEGER,
  next_followup DATE,
  notes TEXT,
  converted_client_id INTEGER,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (assigned_user_id) REFERENCES users(id) ON DELETE SET NULL,
  FOREIGN KEY (converted_client_id) REFERENCES clients(id) ON DELETE SET NULL
);
CREATE TABLE contact_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  lead_id INTEGER,
  client_id INTEGER,
  contact_date DATE NOT NULL,
  channel VARCHAR(40),
  summary TEXT NOT NULL,
  user_id INTEGER,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE,
  FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);
CREATE TABLE marketing_campaigns (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name VARCHAR(190) NOT NULL,
  channel VARCHAR(60),
  start_date DATE,
  end_date DATE,
  budget REAL,
  link VARCHAR(255),
  status VARCHAR(30) NOT NULL DEFAULT 'planned',
  results TEXT,
  notes TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE services (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name VARCHAR(190) NOT NULL,
  description TEXT,
  unit_price REAL NOT NULL DEFAULT 0,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE proposals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id INTEGER,
  lead_id INTEGER,
  title VARCHAR(190) NOT NULL,
  service_id INTEGER,
  amount REAL NOT NULL DEFAULT 0,
  status VARCHAR(30) NOT NULL DEFAULT 'draft',
  valid_until DATE,
  notes TEXT,
  created_by INTEGER,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL,
  FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE SET NULL,
  FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE SET NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE TABLE invoices (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  invoice_number VARCHAR(40) NOT NULL UNIQUE,
  client_id INTEGER NOT NULL,
  proposal_id INTEGER,
  issue_date DATE NOT NULL,
  due_date DATE NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'draft',
  subtotal REAL NOT NULL DEFAULT 0,
  tax_rate REAL NOT NULL DEFAULT 0,
  tax_amount REAL NOT NULL DEFAULT 0,
  total REAL NOT NULL DEFAULT 0,
  notes TEXT,
  created_by INTEGER,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (client_id) REFERENCES clients(id),
  FOREIGN KEY (proposal_id) REFERENCES proposals(id) ON DELETE SET NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX idx_invoices_client ON invoices(client_id);
CREATE INDEX idx_invoices_status ON invoices(status);
CREATE TABLE invoice_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  invoice_id INTEGER NOT NULL,
  service_id INTEGER,
  description VARCHAR(255) NOT NULL,
  quantity REAL NOT NULL DEFAULT 1,
  unit_price REAL NOT NULL DEFAULT 0,
  line_total REAL NOT NULL DEFAULT 0,
  FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
  FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE SET NULL
);
CREATE TABLE payments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  invoice_id INTEGER NOT NULL,
  paid_date DATE NOT NULL,
  amount REAL NOT NULL,
  method VARCHAR(40),
  reference VARCHAR(120),
  recorded_by INTEGER,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
  FOREIGN KEY (recorded_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE TABLE client_requests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id INTEGER NOT NULL,
  user_id INTEGER,
  kind VARCHAR(20) NOT NULL DEFAULT 'request',
  subject VARCHAR(190) NOT NULL,
  message TEXT NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'open',
  response TEXT,
  responded_by INTEGER,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
  FOREIGN KEY (responded_by) REFERENCES users(id) ON DELETE SET NULL
);

-- ===================== FOOTBALL RECORDS =====================
CREATE TABLE clubs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name VARCHAR(190) NOT NULL UNIQUE,
  country VARCHAR(100),
  contact_details TEXT,
  category VARCHAR(60),
  verification_status VARCHAR(30) NOT NULL DEFAULT 'unverified',
  notes TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE teams (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  club_id INTEGER,
  name VARCHAR(190) NOT NULL,
  competition_category VARCHAR(80),
  age_gender_category VARCHAR(60),
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  notes TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (club_id) REFERENCES clubs(id) ON DELETE SET NULL
);
CREATE TABLE players (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  full_name VARCHAR(190) NOT NULL,
  date_of_birth DATE,
  dob_authorised INTEGER NOT NULL DEFAULT 0,
  position VARCHAR(40),
  preferred_foot VARCHAR(20),
  foot_verified INTEGER NOT NULL DEFAULT 0,
  current_team_id INTEGER,
  shirt_number INTEGER,
  nationality VARCHAR(80),
  profile_image VARCHAR(255),
  image_permitted INTEGER NOT NULL DEFAULT 0,
  verification_status VARCHAR(30) NOT NULL DEFAULT 'unverified',
  profile_source VARCHAR(190),
  date_last_verified DATE,
  notes TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (current_team_id) REFERENCES teams(id) ON DELETE SET NULL
);
CREATE INDEX idx_players_team ON players(current_team_id);
CREATE TABLE player_team_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  player_id INTEGER NOT NULL,
  team_id INTEGER NOT NULL,
  start_date DATE,
  end_date DATE,
  shirt_number INTEGER,
  notes TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE,
  FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
);
CREATE TABLE competitions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name VARCHAR(190) NOT NULL,
  organising_body VARCHAR(190),
  category VARCHAR(80),
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  notes TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE seasons (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  competition_id INTEGER NOT NULL,
  name VARCHAR(60) NOT NULL,
  start_date DATE,
  end_date DATE,
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (competition_id) REFERENCES competitions(id) ON DELETE CASCADE
);
CREATE TABLE competition_teams (
  season_id INTEGER NOT NULL,
  team_id INTEGER NOT NULL,
  PRIMARY KEY (season_id, team_id),
  FOREIGN KEY (season_id) REFERENCES seasons(id) ON DELETE CASCADE,
  FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
);
CREATE TABLE venues (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name VARCHAR(190) NOT NULL,
  region VARCHAR(100),
  pitch_details TEXT,
  notes TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE data_sources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name VARCHAR(190) NOT NULL,
  source_type VARCHAR(40) NOT NULL DEFAULT 'live_collection',
  permission_status VARCHAR(30) NOT NULL DEFAULT 'own_collection',
  licence_notes TEXT,
  url VARCHAR(255),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE matches (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  match_code VARCHAR(40) NOT NULL UNIQUE,
  competition_id INTEGER,
  season_id INTEGER,
  home_team_id INTEGER NOT NULL,
  away_team_id INTEGER NOT NULL,
  kickoff DATETIME NOT NULL,
  venue_id INTEGER,
  status VARCHAR(30) NOT NULL DEFAULT 'scheduled',
  duration_minutes INTEGER NOT NULL DEFAULT 90,
  home_score INTEGER,
  away_score INTEGER,
  score_source VARCHAR(190),
  possession_home REAL,
  possession_away REAL,
  possession_source VARCHAR(190),
  attendance INTEGER,
  collection_deadline DATETIME,
  client_id INTEGER,
  notes TEXT,
  created_by INTEGER,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (competition_id) REFERENCES competitions(id) ON DELETE SET NULL,
  FOREIGN KEY (season_id) REFERENCES seasons(id) ON DELETE SET NULL,
  FOREIGN KEY (home_team_id) REFERENCES teams(id),
  FOREIGN KEY (away_team_id) REFERENCES teams(id),
  FOREIGN KEY (venue_id) REFERENCES venues(id) ON DELETE SET NULL,
  FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX idx_matches_status ON matches(status);
CREATE INDEX idx_matches_kickoff ON matches(kickoff);
CREATE TABLE match_status_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  match_id INTEGER NOT NULL,
  old_status VARCHAR(30),
  new_status VARCHAR(30) NOT NULL,
  user_id INTEGER,
  note VARCHAR(255),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);
CREATE TABLE match_checklist_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  match_id INTEGER NOT NULL,
  label VARCHAR(190) NOT NULL,
  done INTEGER NOT NULL DEFAULT 0,
  done_by INTEGER,
  done_at DATETIME,
  FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
  FOREIGN KEY (done_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE TABLE collection_assignments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  match_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  assignment_role VARCHAR(30) NOT NULL,
  deadline DATETIME,
  priority VARCHAR(20) NOT NULL DEFAULT 'normal',
  status VARCHAR(20) NOT NULL DEFAULT 'assigned',
  notes VARCHAR(255),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (match_id, user_id, assignment_role),
  FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE match_collection_scope (
  match_id INTEGER NOT NULL,
  category VARCHAR(30) NOT NULL,
  collected INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (match_id, category),
  FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE
);
CREATE TABLE match_squads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  match_id INTEGER NOT NULL,
  team_id INTEGER NOT NULL,
  player_id INTEGER NOT NULL,
  shirt_number INTEGER,
  is_starter INTEGER NOT NULL DEFAULT 0,
  position VARCHAR(40),
  UNIQUE (match_id, player_id),
  FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
  FOREIGN KEY (team_id) REFERENCES teams(id),
  FOREIGN KEY (player_id) REFERENCES players(id)
);
CREATE TABLE appearances (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  match_id INTEGER NOT NULL,
  team_id INTEGER NOT NULL,
  player_id INTEGER NOT NULL,
  role VARCHAR(20) NOT NULL DEFAULT 'starter',
  start_position VARCHAR(40),
  sub_on_minute INTEGER,
  sub_off_minute INTEGER,
  dismissed_minute INTEGER,
  appearance_status VARCHAR(20) NOT NULL DEFAULT 'played',
  minutes_uncertain INTEGER NOT NULL DEFAULT 0,
  source_id INTEGER,
  verification_status VARCHAR(20) NOT NULL DEFAULT 'unverified',
  UNIQUE (match_id, player_id),
  FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
  FOREIGN KEY (team_id) REFERENCES teams(id),
  FOREIGN KEY (player_id) REFERENCES players(id),
  FOREIGN KEY (source_id) REFERENCES data_sources(id) ON DELETE SET NULL
);

-- ===================== DATA COLLECTION =====================
CREATE TABLE event_types (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code VARCHAR(40) NOT NULL UNIQUE,
  name VARCHAR(80) NOT NULL,
  category VARCHAR(30) NOT NULL,
  scope_category VARCHAR(30) NOT NULL,
  outcomes VARCHAR(255),
  needs_player INTEGER NOT NULL DEFAULT 1,
  related_label VARCHAR(60),
  uses_coords VARCHAR(10) NOT NULL DEFAULT 'none',
  uses_set_piece INTEGER NOT NULL DEFAULT 0,
  sort_order INTEGER NOT NULL DEFAULT 100,
  is_active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE match_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  match_id INTEGER NOT NULL,
  team_id INTEGER NOT NULL,
  player_id INTEGER,
  event_type_id INTEGER NOT NULL,
  period VARCHAR(10) NOT NULL DEFAULT '1H',
  minute INTEGER,
  second INTEGER,
  outcome VARCHAR(40),
  related_player_id INTEGER,
  x_start REAL,
  y_start REAL,
  x_end REAL,
  y_end REAL,
  set_piece_type VARCHAR(30),
  video_timestamp INTEGER,
  collector_id INTEGER,
  source_id INTEGER,
  notes TEXT,
  validation_status VARCHAR(20) NOT NULL DEFAULT 'draft',
  correction_reason VARCHAR(255),
  modified_by INTEGER,
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
);
CREATE INDEX idx_events_match ON match_events(match_id, event_type_id);
CREATE INDEX idx_events_player ON match_events(player_id);
CREATE TABLE validation_issues (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  match_id INTEGER NOT NULL,
  event_id INTEGER,
  issue_type VARCHAR(40) NOT NULL,
  severity VARCHAR(10) NOT NULL DEFAULT 'error',
  message VARCHAR(255) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'open',
  raised_by INTEGER,
  resolved_by INTEGER,
  resolved_at DATETIME,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
  FOREIGN KEY (event_id) REFERENCES match_events(id) ON DELETE SET NULL,
  FOREIGN KEY (raised_by) REFERENCES users(id) ON DELETE SET NULL,
  FOREIGN KEY (resolved_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE TABLE import_jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_type VARCHAR(40) NOT NULL,
  filename VARCHAR(255),
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  rows_total INTEGER NOT NULL DEFAULT 0,
  rows_ok INTEGER NOT NULL DEFAULT 0,
  rows_failed INTEGER NOT NULL DEFAULT 0,
  errors TEXT,
  user_id INTEGER,
  match_id INTEGER,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
  FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE SET NULL
);

-- ===================== ANALYSIS AND SCOUTING =====================
CREATE TABLE metric_definitions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code VARCHAR(40) NOT NULL UNIQUE,
  name VARCHAR(120) NOT NULL,
  subject_scope VARCHAR(20) NOT NULL,
  scope_category VARCHAR(30),
  unit VARCHAR(20),
  formula TEXT NOT NULL,
  definition TEXT,
  test_example TEXT
);
CREATE TABLE analysis_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  match_id INTEGER NOT NULL,
  run_by INTEGER,
  data_status VARCHAR(20) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'complete',
  notes VARCHAR(255),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
  FOREIGN KEY (run_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE TABLE metric_values (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  analysis_run_id INTEGER NOT NULL,
  subject_type VARCHAR(10) NOT NULL,
  subject_id INTEGER NOT NULL,
  metric_code VARCHAR(40) NOT NULL,
  value REAL,
  status VARCHAR(20) NOT NULL,
  note VARCHAR(255),
  basis_matches INTEGER,
  of_matches INTEGER,
  FOREIGN KEY (analysis_run_id) REFERENCES analysis_runs(id) ON DELETE CASCADE
);
CREATE INDEX idx_metric_run ON metric_values(analysis_run_id, subject_type, subject_id);
CREATE TABLE analyst_notes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  match_id INTEGER,
  player_id INTEGER,
  team_id INTEGER,
  author_id INTEGER,
  note_type VARCHAR(30) NOT NULL,
  body TEXT NOT NULL,
  is_fact INTEGER NOT NULL DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
  FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE SET NULL,
  FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE SET NULL,
  FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE SET NULL
);
CREATE TABLE video_assets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title VARCHAR(190) NOT NULL,
  match_id INTEGER,
  reference VARCHAR(255),
  file_path VARCHAR(255),
  permission_status VARCHAR(20) NOT NULL DEFAULT 'pending',
  licence_notes TEXT,
  access_restriction VARCHAR(30) NOT NULL DEFAULT 'internal_only',
  uploaded_by INTEGER,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE SET NULL,
  FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE TABLE video_clips (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  video_id INTEGER NOT NULL,
  match_id INTEGER,
  player_id INTEGER,
  start_seconds INTEGER NOT NULL,
  end_seconds INTEGER,
  event_category VARCHAR(40),
  tags VARCHAR(255),
  notes TEXT,
  created_by INTEGER,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (video_id) REFERENCES video_assets(id) ON DELETE CASCADE,
  FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE SET NULL,
  FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE SET NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE TABLE scouting_reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  player_id INTEGER NOT NULL,
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
  analyst_id INTEGER,
  review_status VARCHAR(20) NOT NULL DEFAULT 'draft',
  reviewer_id INTEGER,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (player_id) REFERENCES players(id),
  FOREIGN KEY (analyst_id) REFERENCES users(id) ON DELETE SET NULL,
  FOREIGN KEY (reviewer_id) REFERENCES users(id) ON DELETE SET NULL
);
CREATE TABLE scouting_report_matches (
  scouting_id INTEGER NOT NULL,
  match_id INTEGER NOT NULL,
  PRIMARY KEY (scouting_id, match_id),
  FOREIGN KEY (scouting_id) REFERENCES scouting_reports(id) ON DELETE CASCADE,
  FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE
);

-- ===================== REPORTS AND WORKFLOW =====================
CREATE TABLE reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  report_type VARCHAR(20) NOT NULL,
  title VARCHAR(190) NOT NULL,
  match_id INTEGER,
  player_id INTEGER,
  team_id INTEGER,
  scouting_id INTEGER,
  client_id INTEGER,
  status VARCHAR(20) NOT NULL DEFAULT 'draft',
  data_status VARCHAR(20) NOT NULL DEFAULT 'validated',
  current_version INTEGER NOT NULL DEFAULT 0,
  content TEXT,
  created_by INTEGER,
  reviewer_id INTEGER,
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
);
CREATE INDEX idx_reports_status ON reports(status);
CREATE TABLE report_versions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  report_id INTEGER NOT NULL,
  version INTEGER NOT NULL,
  content TEXT NOT NULL,
  pdf_path VARCHAR(255),
  analysis_run_id INTEGER,
  created_by INTEGER,
  note VARCHAR(255),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (report_id, version),
  FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE,
  FOREIGN KEY (analysis_run_id) REFERENCES analysis_runs(id) ON DELETE SET NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE TABLE report_shares (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  report_id INTEGER NOT NULL,
  client_id INTEGER NOT NULL,
  version INTEGER NOT NULL,
  shared_by INTEGER,
  shared_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  status VARCHAR(20) NOT NULL DEFAULT 'delivered',
  viewed_at DATETIME,
  downloaded_at DATETIME,
  FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE,
  FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
  FOREIGN KEY (shared_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE TABLE tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title VARCHAR(190) NOT NULL,
  description TEXT,
  assigned_to INTEGER,
  department VARCHAR(40),
  priority VARCHAR(20) NOT NULL DEFAULT 'normal',
  due_date DATE,
  status VARCHAR(20) NOT NULL DEFAULT 'open',
  related_type VARCHAR(20),
  related_id INTEGER,
  notes TEXT,
  created_by INTEGER,
  completed_at DATETIME,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (assigned_to) REFERENCES users(id) ON DELETE SET NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX idx_tasks_assignee ON tasks(assigned_to, status);
CREATE TABLE expenses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  expense_date DATE NOT NULL,
  category VARCHAR(60) NOT NULL,
  description VARCHAR(255) NOT NULL,
  amount REAL NOT NULL,
  payee VARCHAR(150),
  receipt_ref VARCHAR(190),
  related_match_id INTEGER,
  related_client_id INTEGER,
  recorded_by INTEGER,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (related_match_id) REFERENCES matches(id) ON DELETE SET NULL,
  FOREIGN KEY (related_client_id) REFERENCES clients(id) ON DELETE SET NULL,
  FOREIGN KEY (recorded_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE TABLE backup_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  action VARCHAR(30) NOT NULL,
  file_path VARCHAR(255),
  size_bytes INTEGER,
  status VARCHAR(20) NOT NULL,
  message VARCHAR(255),
  user_id INTEGER,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);
