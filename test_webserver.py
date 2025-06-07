import requests
import time

BASE_URL = "http://127.0.0.1:5000"

def test_verify_missing_params():
    r = requests.get(f"{BASE_URL}/verify")
    assert r.status_code == 400
    assert "Missing uid or file_id" in r.text

def test_verify_invalid_uid():
    r = requests.get(f"{BASE_URL}/verify?uid=abc&file_id=123")
    assert r.status_code == 400
    assert "Invalid user ID" in r.text

def test_verify_valid():
    # Use dummy valid user_id and file_id
    user_id = 123456
    file_id = "testfile123"
    r = requests.get(f"{BASE_URL}/verify?uid={user_id}&file_id={file_id}")
    assert r.status_code == 200
    assert "Verification Successful" in r.text

def test_health():
    r = requests.get(f"{BASE_URL}/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "✅ healthy"
    assert "timestamp" in data

if __name__ == "__main__":
    print("Starting tests...")
    test_verify_missing_params()
    print("test_verify_missing_params passed")
    test_verify_invalid_uid()
    print("test_verify_invalid_uid passed")
    test_verify_valid()
    print("test_verify_valid passed")
    test_health()
    print("test_health passed")
    print("All tests passed successfully.")
