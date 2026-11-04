"""NT-04 load profile for NFR-06.

Start the stack, seed the data, then run:

    docker compose exec api python manage.py seed_load_data
    locust -f loadtests/locustfile.py --headless -u 30 -r 3 -t 3m --host http://localhost:8080

Each simulated user signs in once. The password is DEMO_PASSWORD from .env.
"""

import os

from locust import HttpUser, between, task

PASSWORD = os.environ.get("DEMO_PASSWORD", "change-me-demo-password")


class SignedInUser(HttpUser):
    abstract = True
    wait_time = between(1, 3)
    email = ""

    def on_start(self):
        token = self.client.get("/api/auth/csrf").json()["csrfToken"]
        self.client.headers["Cookie"] = f"csrftoken={token}"
        response = self.client.post(
            "/api/auth/login",
            json={"email": self.email, "password": PASSWORD},
            headers={"X-CSRFToken": token},
        )
        # The cookies are marked Secure, and this client talks plain HTTP to the local proxy,
        # so it would not send them back by itself.
        self.client.headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in response.cookies.items())


class Resident(SignedInUser):
    weight = 6
    email = "resident@example.test"

    @task(4)
    def my_requests(self):
        self.client.get("/api/requests/?mine=true")

    @task(1)
    def form_options(self):
        self.client.get("/api/locations/")
        self.client.get("/api/categories/")


class Supervisor(SignedInUser):
    weight = 2
    email = "supervisor@example.test"

    @task(3)
    def triage_queue(self):
        self.client.get("/api/triage-queue/")

    @task(1)
    def dashboard(self):
        self.client.get("/api/dashboard/")

    @task(1)
    def technicians(self):
        self.client.get("/api/technicians/")


class Technician(SignedInUser):
    weight = 1
    email = "technician@example.test"

    @task
    def work_queue(self):
        self.client.get("/api/work-queue/")


class Warden(SignedInUser):
    weight = 1
    email = "warden@example.test"

    @task
    def dashboard(self):
        self.client.get("/api/dashboard/")
