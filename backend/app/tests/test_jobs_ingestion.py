def test_job_ingestion_success(client):
    file_content = b"test image content"
    files = {"files": ("test_image.jpeg", file_content, "image/jpeg")}
    data = {"title": "Fix my sink", "description": "It is leaking"}

    response = client.post("/api/v1/jobs/ingest", data=data, files=files)
    assert response.status_code == 202
    res_data = response.json()
    assert "Job successfully ingested" in res_data["message"]
    assert "job_id" in res_data


def test_job_ingestion_blurry_rejection(client):
    file_content = b"test image content"
    files = {"files": ("blurry_image.jpeg", file_content, "image/jpeg")}
    data = {"title": "Fix my sink", "description": "It is leaking"}

    response = client.post("/api/v1/jobs/ingest", data=data, files=files)
    assert response.status_code == 400
    res_data = response.json()
    assert res_data["message"] == "Media Quality Validation Failed"
    assert "I can't see the underside of the beam" in res_data["details"]["feedback"]


def test_job_ingestion_invalid_file_type(client):
    file_content = b"test text content"
    files = {"files": ("test.txt", file_content, "text/plain")}
    data = {"title": "Fix my sink", "description": "It is leaking"}

    response = client.post("/api/v1/jobs/ingest", data=data, files=files)
    assert response.status_code == 400
    res_data = response.json()
    assert "Unsupported file type" in res_data["message"]
