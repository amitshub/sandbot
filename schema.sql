CREATE TABLE tenants (
  id INT AUTO_INCREMENT PRIMARY KEY,
  slug VARCHAR(100) NOT NULL UNIQUE,
  tenant_name VARCHAR(255) NOT NULL,

  allowed_hosts JSON NULL,
  frontend_paths JSON NULL,

  client_domain VARCHAR(255) NULL,
  branding_api VARCHAR(255) NULL,

  db_host VARCHAR(255) NULL,
  db_port INT DEFAULT 3306,
  db_user VARCHAR(255) NULL,
  db_password VARCHAR(255) NULL,
  db_name VARCHAR(255) NULL,

  faiss_index_path VARCHAR(500) NULL,

  plan_name VARCHAR(100) DEFAULT 'free',
  status ENUM('active','inactive','suspended') DEFAULT 'active',

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

ALTER TABLE tenants
ADD COLUMN whatsapp_provider ENUM('meta','twilio') NULL DEFAULT NULL,
ADD COLUMN meta_access_token TEXT NULL,
ADD COLUMN meta_phone_number_id VARCHAR(255) NULL,
ADD COLUMN meta_business_account_id VARCHAR(255) NULL,
ADD COLUMN whatsapp_number VARCHAR(30) NULL;

ALTER TABLE tenants
ADD COLUMN twilio_account_sid VARCHAR(255) NULL AFTER db_name,
ADD COLUMN twilio_auth_token VARCHAR(255) NULL AFTER twilio_account_sid,
ADD COLUMN twilio_phone_number VARCHAR(30) NULL AFTER twilio_auth_token;

ALTER TABLE tenants
ADD COLUMN whatsapp_verify_token VARCHAR(255) NULL;

-- twilio_account_sid
-- twilio_auth_token
-- twilio_phone_number

CREATE TABLE tenant_users (
  id INT AUTO_INCREMENT PRIMARY KEY,

  tenant_id INT NOT NULL,

  name VARCHAR(255) NULL,
  email VARCHAR(255) NOT NULL,
  password_hash VARCHAR(255) NULL,

  auth_provider ENUM('local','google') DEFAULT 'local',
  google_sub VARCHAR(255) NULL,

  role ENUM('owner','admin','member') DEFAULT 'owner',
  status ENUM('active','inactive','blocked') DEFAULT 'active',

  last_login_at DATETIME NULL,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  UNIQUE KEY unique_email_per_tenant (email, tenant_id),

  CONSTRAINT fk_tenant_users_tenant
    FOREIGN KEY (tenant_id)
    REFERENCES tenants(id)
    ON DELETE CASCADE
);


CREATE TABLE tenant_customers (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,

  tenant_id INT NOT NULL,

  session_id VARCHAR(150) NOT NULL,

  name VARCHAR(255) NULL,
  email VARCHAR(255) NULL,
  phone VARCHAR(50) NULL,

  first_message TEXT NULL,
  last_message TEXT NULL,

  source VARCHAR(100) DEFAULT 'public_chat',
  status ENUM('new','active','converted','blocked') DEFAULT 'new',

  user_agent TEXT NULL,
  ip_address VARCHAR(100) NULL,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  last_seen_at DATETIME NULL,

  UNIQUE KEY unique_tenant_session (tenant_id, session_id),
  KEY idx_tenant_email (tenant_id, email),
  KEY idx_tenant_status (tenant_id, status),

  CONSTRAINT fk_tenant_customers_tenant
    FOREIGN KEY (tenant_id)
    REFERENCES tenants(id)
    ON DELETE CASCADE
); 

CREATE TABLE tenant_agent_settings (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  tenant_id INT NOT NULL UNIQUE,

  business_name VARCHAR(255) NULL,
  industry VARCHAR(255) NULL,
  business_type VARCHAR(255) NULL,
  business_description TEXT NULL,

  greeting_message TEXT NULL,
  starter_questions JSON NULL,

  system_prompt TEXT NULL,
  restriction_rules TEXT NULL,
  support_hours JSON NULL,

  last_training_summary JSON NULL,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  CONSTRAINT fk_tenant_agent_settings_tenant
    FOREIGN KEY (tenant_id)
    REFERENCES tenants(id)
    ON DELETE CASCADE
); 

CREATE TABLE tenant_public_links (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    tenant_id INT NOT NULL UNIQUE,
    tenant_slug VARCHAR(100) NOT NULL,
    short_code VARCHAR(8) NOT NULL UNIQUE,
    sweet_name VARCHAR(100) NULL UNIQUE,
    target_path VARCHAR(255) NOT NULL,
    is_active TINYINT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE t_integration (
    id INT AUTO_INCREMENT PRIMARY KEY,

    tenant_id INT NULL,
    tenant_slug VARCHAR(100) NULL,

    company_name VARCHAR(255) NULL,
    platform ENUM('wordpress','shopify','wix','react','html','nextjs') NOT NULL,

    db_host VARCHAR(255) NOT NULL,
    db_port INT DEFAULT 3306,
    db_user VARCHAR(255) NOT NULL,
    db_password TEXT NOT NULL,
    db_name VARCHAR(255) NOT NULL,

    website_url VARCHAR(500) NULL,
    status ENUM('active','inactive') DEFAULT 'active',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);