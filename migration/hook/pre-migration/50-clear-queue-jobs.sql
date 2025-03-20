-- X-Modules: queue_job
DELETE FROM queue_job_queue_jobs_to_done_rel;
DELETE FROM queue_job_queue_requeue_job_rel;
DELETE FROM queue_job;