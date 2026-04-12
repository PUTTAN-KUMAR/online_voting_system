CREATE DATABASE voting_system;

USE voting_system;

-- Users Table
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    role ENUM('voter', 'admin') DEFAULT 'voter',
    has_voted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Candidates Table
CREATE TABLE candidates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    party VARCHAR(50),
    photo VARCHAR(255),
    position VARCHAR(50),
    votes INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Votes Table
CREATE TABLE votes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    candidate_id INT,
    position VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (candidate_id) REFERENCES candidates (id),
    UNIQUE KEY unique_vote (user_id, position)
);

-- Insert Sample Data
INSERT INTO
    users (
        username,
        email,
        password,
        role
    )
VALUES (
        'admin',
        'admin@voting.com',
        '$2b$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi',
        'admin'
    ),
    (
        'voter1',
        'voter1@gmail.com',
        '$2b$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi',
        'voter'
    );

INSERT INTO
    candidates (name, party, position)
VALUES (
        'Amit Shah',
        'BJP',
        'President'
    ),
    (
        'Rahul Gandhi',
        'Congress',
        'President'
    ),
    (
        'Arvind Kejriwal',
        'AAP',
        'President'
    ),
    (
        'Mamata Banerjee',
        'TMC',
        'President'
    );