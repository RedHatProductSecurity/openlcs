DROP TABLE IF EXISTS celery_taskmeta, celery_tasksetmeta;
DROP SEQUENCE IF EXISTS task_id_sequence, taskset_id_sequence;

CREATE TABLE celery_taskmeta (
    id integer NOT NULL,
    task_id character varying(155),
    status character varying(50),
    result bytea,
    date_done timestamp without time zone,
    traceback text,
    name character varying(155),
    args bytea,
    kwargs bytea,
    worker character varying(155),
    retries integer,
    queue character varying(155)
);

ALTER TABLE ONLY celery_taskmeta
    ADD CONSTRAINT celery_taskmeta_pkey PRIMARY KEY (id);
ALTER TABLE ONLY celery_taskmeta
    ADD CONSTRAINT celery_taskmeta_task_id_key UNIQUE (task_id);
CREATE SEQUENCE task_id_sequence
               START WITH 1
               INCREMENT BY 1
               NO MINVALUE
               NO MAXVALUE
               CACHE 1;

CREATE TABLE celery_tasksetmeta (
    id integer NOT NULL,
    taskset_id character varying(155),
    result bytea,
    date_done timestamp without time zone
);

ALTER TABLE celery_tasksetmeta
    ADD CONSTRAINT celery_tasksetmeta_pkey PRIMARY KEY (id);
ALTER TABLE celery_tasksetmeta
    ADD CONSTRAINT celery_tasksetmeta_taskset_id_key UNIQUE (taskset_id);
CREATE SEQUENCE taskset_id_sequence
               START WITH 1
               INCREMENT BY 1
               NO MINVALUE
               NO MAXVALUE
               CACHE 1;
