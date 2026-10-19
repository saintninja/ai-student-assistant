CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE users (
  id            bigserial PRIMARY KEY,
  ins           text UNIQUE NOT NULL,              
  full_name     text NOT NULL,
  group_name    text,
  role          text NOT NULL DEFAULT 'student' CHECK (role IN ('student','admin')),
  password_hash text NOT NULL,                     
  is_active     boolean NOT NULL DEFAULT true,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE disciplines (id serial PRIMARY KEY, code text UNIQUE NOT NULL, title text NOT NULL);
CREATE TABLE topics (
  id serial PRIMARY KEY,
  discipline_id int NOT NULL REFERENCES disciplines(id),
  title text NOT NULL, description text,
  UNIQUE (discipline_id, title)
);

CREATE TABLE tasks (
  id                 bigserial PRIMARY KEY,
  code               text GENERATED ALWAYS AS ('T-' || lpad(id::text, 6, '0')) STORED UNIQUE,  
  topic_id           int NOT NULL REFERENCES topics(id),
  title              text NOT NULL,
  statement          text NOT NULL,
  difficulty         smallint NOT NULL CHECK (difficulty BETWEEN 1 AND 5),
  answer_type        text NOT NULL CHECK (answer_type IN ('exact','numeric','free')),
  reference_answer   text,                         
  reference_solution text NOT NULL,                
  expected_minutes   int NOT NULL DEFAULT 10,
  source             text NOT NULL CHECK (source IN ('manual','generated')),
  status             text NOT NULL DEFAULT 'approved' CHECK (status IN ('approved','auto','rejected')),
  embedding          vector(1024),                 
  created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON tasks (topic_id, status);

CREATE TABLE task_hints (                           
  task_id bigint REFERENCES tasks(id) ON DELETE CASCADE,
  level smallint CHECK (level BETWEEN 1 AND 3),
  text text NOT NULL,
  PRIMARY KEY (task_id, level)
);

CREATE TABLE attempts (                             
  id               bigserial PRIMARY KEY,
  user_id          bigint NOT NULL REFERENCES users(id),
  task_id          bigint NOT NULL REFERENCES tasks(id),
  mode             text NOT NULL CHECK (mode IN ('topic','general')),
  started_at       timestamptz NOT NULL DEFAULT now(),
  last_activity_at timestamptz NOT NULL DEFAULT now(),
  active_seconds   int NOT NULL DEFAULT 0,          
  hints_used       int NOT NULL DEFAULT 0,
  wrong_submissions int NOT NULL DEFAULT 0,
  solved_at        timestamptz
);
CREATE UNIQUE INDEX one_open_attempt ON attempts (user_id, task_id) WHERE solved_at IS NULL;

CREATE TABLE submissions (
  id bigserial PRIMARY KEY, attempt_id bigint NOT NULL REFERENCES attempts(id),
  answer text NOT NULL, is_correct boolean NOT NULL, comment text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE hint_requests (
  id bigserial PRIMARY KEY, attempt_id bigint NOT NULL REFERENCES attempts(id),
  level smallint NOT NULL, question text, cached boolean NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE kb_documents (
  id bigserial PRIMARY KEY,
  discipline_id int NOT NULL REFERENCES disciplines(id),
  topic_id int REFERENCES topics(id),
  doc_type text NOT NULL CHECK (doc_type IN ('theory','example','pitfall','task_pattern','glossary')),
  title text NOT NULL, source text, checksum text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE kb_chunks (
  id bigserial PRIMARY KEY,
  document_id bigint NOT NULL REFERENCES kb_documents(id) ON DELETE CASCADE,
  discipline_id int NOT NULL, topic_id int, doc_type text NOT NULL,   
  chunk_index int NOT NULL, heading text, content text NOT NULL,
  embedding vector(1024) NOT NULL
);
CREATE INDEX ON kb_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON kb_chunks (topic_id, doc_type);

CREATE FUNCTION attempt_weakness(solved boolean, sec int, exp_min int, hints int, wrong int)
RETURNS double precision LANGUAGE sql IMMUTABLE AS $$
  SELECT (CASE WHEN NOT solved THEN 1.0
    ELSE 0.4 * LEAST(GREATEST(sec / (exp_min * 60.0) - 1, 0), 1)   
       + 0.4 * LEAST(hints / 3.0, 1)                               
       + 0.2 * LEAST(wrong / 3.0, 1)                               
  END)::double precision $$;

CREATE VIEW v_attempt_weakness AS
SELECT a.id AS attempt_id, a.user_id, a.task_id, k.topic_id,
       attempt_weakness(a.solved_at IS NOT NULL, a.active_seconds, k.expected_minutes,
                        a.hints_used, a.wrong_submissions) AS w
FROM attempts a JOIN tasks k ON k.id = a.task_id
WHERE a.solved_at IS NOT NULL                       
   OR (a.last_activity_at < now() - interval '1 hour'   -- not solved
       AND (a.hints_used > 0 OR a.wrong_submissions > 0 OR a.active_seconds >= 60));

CREATE VIEW v_student_topic_stats AS
SELECT u.id AS user_id, u.ins, u.full_name, d.id AS discipline_id, d.title AS discipline,
       t.id AS topic_id, t.title AS topic,
       (SELECT count(*) FROM tasks x WHERE x.topic_id = t.id AND x.status <> 'rejected') AS tasks_total,
       count(DISTINCT a.task_id)                          AS tasks_attempted,
       count(DISTINCT a.task_id) FILTER (WHERE a.solved_at IS NOT NULL) AS tasks_solved,
       coalesce(sum(a.hints_used), 0)                     AS hints_requested,
       coalesce(sum(a.active_seconds), 0)                 AS seconds_spent
FROM users u
JOIN attempts a    ON a.user_id = u.id
JOIN tasks k       ON k.id = a.task_id
JOIN topics t      ON t.id = k.topic_id
JOIN disciplines d ON d.id = t.discipline_id
GROUP BY u.id, u.ins, u.full_name, d.id, d.title, t.id, t.title;