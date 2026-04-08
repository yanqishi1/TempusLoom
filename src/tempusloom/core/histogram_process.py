from __future__ import annotations

from queue import Empty

from .tl_image import TLImage


def histogram_worker_main(
    request_queue,
    result_queue,
    *,
    render_dimension: int = 480,
    histogram_dimension: int = 480,
) -> None:
    while True:
        task = request_queue.get()
        if task is None or task.get("type") == "stop":
            return

        latest_task = task
        while True:
            try:
                candidate = request_queue.get_nowait()
            except Empty:
                break
            if candidate is None or candidate.get("type") == "stop":
                return
            latest_task = candidate

        job_id = int(latest_task.get("job_id", 0))
        snapshot = latest_task.get("snapshot")

        try:
            tl_image = TLImage.from_dict(snapshot)
            rendered = tl_image.render_image(preview=True, max_dimension=render_dimension)
            histogram = TLImage.histogram_from_image(
                rendered,
                sample_max_dimension=histogram_dimension,
            )
            result_queue.put(
                {
                    "job_id": job_id,
                    "histogram": histogram,
                    "metadata": dict(tl_image.metadata),
                }
            )
        except Exception as exc:
            result_queue.put(
                {
                    "job_id": job_id,
                    "error": str(exc),
                }
            )
