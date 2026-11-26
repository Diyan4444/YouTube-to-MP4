import os
import unittest
import json
import tempfile
import time
import shutil

# Ensure backend directory is in path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import app
from app import extract_canonical_video_id, ALLOWED_QUALITIES, ALLOWED_BITRATES

class TestYouTubeUtility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.app.config["TESTING"] = True
        cls.client = app.app.test_client()

    def test_url_canonical_validation(self):
        """Test URL parsing, domain isolation and canonical ID extraction."""
        # Valid URLs
        self.assertEqual(extract_canonical_video_id("https://www.youtube.com/watch?v=KsHQtipHwOc"), "KsHQtipHwOc")
        self.assertEqual(extract_canonical_video_id("https://youtu.be/KsHQtipHwOc"), "KsHQtipHwOc")
        self.assertEqual(extract_canonical_video_id("https://m.youtube.com/watch?v=KsHQtipHwOc&t=42s"), "KsHQtipHwOc")
        self.assertEqual(extract_canonical_video_id("https://www.youtube.com/shorts/KsHQtipHwOc"), "KsHQtipHwOc")
        self.assertEqual(extract_canonical_video_id("https://www.youtube.com/embed/KsHQtipHwOc"), "KsHQtipHwOc")

        # Invalid or Malicious URLs
        self.assertIsNone(extract_canonical_video_id("https://attacker.com/watch?v=KsHQtipHwOc"))
        self.assertIsNone(extract_canonical_video_id("https://youtube.com.attacker.com/watch?v=KsHQtipHwOc"))
        self.assertIsNone(extract_canonical_video_id("javascript:alert(1)"))
        self.assertIsNone(extract_canonical_video_id("file:///etc/passwd"))
        self.assertIsNone(extract_canonical_video_id("https://www.youtube.com/watch?v=invalid_id_too_long"))
        self.assertIsNone(extract_canonical_video_id(""))
        self.assertIsNone(extract_canonical_video_id(None))

    def test_health_endpoint(self):
        """Test health endpoint returns healthy state and metadata."""
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("ffmpeg", data)
        self.assertIn("max_concurrent", data)

    def test_api_formats_validation(self):
        """Test payload validation on /api/formats."""
        # Missing body
        res = self.client.post("/api/formats", data="")
        self.assertEqual(res.status_code, 400)

        # Invalid URL
        res = self.client.post("/api/formats", json={"url": "https://google.com"})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertIn("error", data)

    def test_start_download_validation(self):
        """Test validation on /api/start-download."""
        # Missing URL
        res = self.client.post("/api/start-download", json={"type": "mp4", "quality": 1080})
        self.assertEqual(res.status_code, 400)

        # Unsupported media type
        res = self.client.post("/api/start-download", json={
            "url": "https://www.youtube.com/watch?v=KsHQtipHwOc",
            "type": "avi",
            "quality": 720
        })
        self.assertEqual(res.status_code, 400)

        # Unsupported video quality
        res = self.client.post("/api/start-download", json={
            "url": "https://www.youtube.com/watch?v=KsHQtipHwOc",
            "type": "mp4",
            "quality": 9999
        })
        self.assertEqual(res.status_code, 400)

        # Unsupported audio bitrate
        res = self.client.post("/api/start-download", json={
            "url": "https://www.youtube.com/watch?v=KsHQtipHwOc",
            "type": "mp3",
            "quality": "999"
        })
        self.assertEqual(res.status_code, 400)

    def test_sqlite_job_lifecycle(self):
        """Test job creation, updating, polling, and SQLite persistence."""
        job_id = "test-job-lifecycle-123"
        now = time.time()
        with app.get_db() as conn:
            conn.execute("""
                INSERT INTO jobs (id, url, video_id, media_type, quality, status, progress, stage, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (job_id, "https://www.youtube.com/watch?v=KsHQtipHwOc", "KsHQtipHwOc", "mp4", "720", "downloading", 45.5, "Downloading...", now, now))

        # Check via progress endpoint
        res = self.client.get(f"/api/progress/{job_id}")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "downloading")
        self.assertEqual(data["progress"], 45.5)

        # Update job to completed
        app.update_job(job_id, status="completed", progress=100.0, stage="Ready")
        res = self.client.get(f"/api/progress/{job_id}")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["progress"], 100.0)

        # Cleanup test job
        with app.get_db() as conn:
            conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))

    def test_download_cancellation(self):
        """Test user cancellation endpoint."""
        job_id = "test-cancel-job-456"
        now = time.time()
        with app.get_db() as conn:
            conn.execute("""
                INSERT INTO jobs (id, url, video_id, media_type, quality, status, progress, stage, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (job_id, "https://www.youtube.com/watch?v=KsHQtipHwOc", "KsHQtipHwOc", "mp4", "1080", "waiting", 0.0, "Waiting...", now, now))

        res = self.client.post(f"/api/cancel/{job_id}")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])

        # Check job status is now cancelled
        job = app.get_job(job_id)
        self.assertEqual(job["status"], "cancelled")

        # Cleanup
        with app.get_db() as conn:
            conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))

    def test_path_traversal_protection(self):
        """Test that directory traversal attempts are blocked when accessing /download-file."""
        job_id = "test-path-traversal-789"
        now = time.time()
        with app.get_db() as conn:
            conn.execute("""
                INSERT INTO jobs (id, url, video_id, media_type, quality, status, progress, file_path, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (job_id, "url", "vid", "mp4", "1080", "completed", 100.0, "C:\\Windows\\System32\\drivers\\etc\\hosts", now, now))

        res = self.client.get(f"/api/download-file/{job_id}")
        # Must deny access since path is outside DOWNLOAD_ROOT
        self.assertIn(res.status_code, (403, 404))

        # Cleanup
        with app.get_db() as conn:
            conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))

if __name__ == "__main__":
    unittest.main()
