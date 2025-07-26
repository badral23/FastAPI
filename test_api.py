#!/usr/bin/env python3
"""
Comprehensive API Test Suite for Hii Box API
Tests all endpoints including authentication, CRUD operations, and edge cases.
"""

import requests
import json
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class TestConfig:
    """Test configuration"""
    BASE_URL: str = "http://0.0.0.0:8000/api/v1"
    # Your existing login credentials from earlier
    WALLET_ADDRESS: str = ""
    ACCESS_TOKEN: str = ""
    TIMEOUT: int = 30


class APITester:
    def __init__(self, config: TestConfig):
        self.config = config
        self.session = requests.Session()
        self.test_results = []
        self.user_id = None
        self.created_nft_id = None
        self.created_social_id = None

        # Set default headers
        self.auth_headers = {
            "Authorization": f"Bearer {config.ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }

    def log_test(self, test_name: str, status: str, details: str = ""):
        """Log test results"""
        result = {
            "test": test_name,
            "status": status,
            "details": details,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.test_results.append(result)

        # Color coding for console output
        color = "\033[92m" if status == "PASS" else "\033[91m" if status == "FAIL" else "\033[93m"
        reset = "\033[0m"
        print(f"{color}[{status}]{reset} {test_name}: {details}")

    def make_request(self, method: str, endpoint: str, data: Dict = None,
                     headers: Dict = None, use_auth: bool = True) -> requests.Response:
        """Make HTTP request with proper error handling"""
        url = f"{self.config.BASE_URL}{endpoint}"

        # Use auth headers by default
        request_headers = self.auth_headers.copy() if use_auth else {"Content-Type": "application/json"}
        if headers:
            request_headers.update(headers)

        try:
            if method.upper() == "GET":
                response = self.session.get(url, headers=request_headers, timeout=self.config.TIMEOUT)
            elif method.upper() == "POST":
                response = self.session.post(url, json=data, headers=request_headers, timeout=self.config.TIMEOUT)
            elif method.upper() == "PUT":
                response = self.session.put(url, json=data, headers=request_headers, timeout=self.config.TIMEOUT)
            elif method.upper() == "PATCH":
                response = self.session.patch(url, json=data, headers=request_headers, timeout=self.config.TIMEOUT)
            elif method.upper() == "DELETE":
                response = self.session.delete(url, headers=request_headers, timeout=self.config.TIMEOUT)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            return response
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            raise

    # ============= HEALTH CHECK TESTS =============
    def test_health_check(self):
        """Test health endpoint (no auth required)"""
        try:
            response = self.make_request("GET", "/health", use_auth=False)

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy":
                    self.log_test("Health Check", "PASS", f"API is healthy")
                else:
                    self.log_test("Health Check", "FAIL", f"Unexpected response: {data}")
            else:
                self.log_test("Health Check", "FAIL", f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Health Check", "FAIL", f"Exception: {str(e)}")

    # ============= AUTHENTICATION TESTS =============
    def test_login_endpoint(self):
        """Test login endpoint (already authenticated, so just verify it exists)"""
        # This is a public endpoint, but we'll test with invalid data to verify it exists
        try:
            invalid_login_data = {
                "wallet_address": "0xinvalid",
                "signed_message": "invalid",
                "message": "invalid"
            }
            response = self.make_request("POST", "/login", data=invalid_login_data, use_auth=False)

            # Should get 400 for invalid signature, not 404
            if response.status_code in [400, 422]:
                self.log_test("Login Endpoint", "PASS", f"Login endpoint exists and validates input")
            else:
                self.log_test("Login Endpoint", "FAIL", f"Unexpected status: {response.status_code}")
        except Exception as e:
            self.log_test("Login Endpoint", "FAIL", f"Exception: {str(e)}")

    # ============= USER PROFILE TESTS =============
    def test_get_current_user(self):
        """Test GET /users/me"""
        try:
            response = self.make_request("GET", "/users/me")

            if response.status_code == 200:
                user_data = response.json()
                self.user_id = user_data.get("id")
                wallet = user_data.get("wallet_address")

                if wallet == self.config.WALLET_ADDRESS:
                    self.log_test("Get Current User", "PASS", f"User ID: {self.user_id}, Wallet: {wallet}")
                else:
                    self.log_test("Get Current User", "FAIL",
                                  f"Wallet mismatch: expected {self.config.WALLET_ADDRESS}, got {wallet}")
            else:
                self.log_test("Get Current User", "FAIL", f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            self.log_test("Get Current User", "FAIL", f"Exception: {str(e)}")

    def test_get_user_keys(self):
        """Test GET /users/me/keys"""
        try:
            response = self.make_request("GET", "/users/me/keys")

            if response.status_code == 200:
                data = response.json()
                key_count = data.get("key_count")
                self.log_test("Get User Keys", "PASS", f"Key count: {key_count}")
            else:
                self.log_test("Get User Keys", "FAIL", f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Get User Keys", "FAIL", f"Exception: {str(e)}")

    def test_get_campaign_status(self):
        """Test GET /users/me/campaign-status"""
        try:
            response = self.make_request("GET", "/users/me/campaign-status")

            if response.status_code == 200:
                data = response.json()
                nft_count = data.get("nft_count")
                social_count = data.get("social_count")
                self.log_test("Get Campaign Status", "PASS", f"NFTs: {nft_count}, Socials: {social_count}")
            else:
                self.log_test("Get Campaign Status", "FAIL", f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Get Campaign Status", "FAIL", f"Exception: {str(e)}")

    # ============= NFT TESTS =============
    def test_create_user_nft(self):
        """Test POST /user_nft"""
        if not self.user_id:
            self.log_test("Create User NFT", "SKIP", "No user_id available")
            return

        try:
            nft_data = {
                "user_id": self.user_id,
                "nft_collection": "BoredApeYachtClub",
                "nft_id": "1234",
                "used": False
            }
            response = self.make_request("POST", "/user_nft", data=nft_data)

            if response.status_code == 201:
                created_nft = response.json()
                self.created_nft_id = created_nft.get("id")
                self.log_test("Create User NFT", "PASS", f"Created NFT ID: {self.created_nft_id}")
            else:
                self.log_test("Create User NFT", "FAIL", f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            self.log_test("Create User NFT", "FAIL", f"Exception: {str(e)}")

    def test_get_user_nfts(self):
        """Test GET /users/me/nfts"""
        try:
            response = self.make_request("GET", "/users/me/nfts")

            if response.status_code == 200:
                nfts = response.json()
                self.log_test("Get User NFTs", "PASS", f"Found {len(nfts)} NFTs")
            else:
                self.log_test("Get User NFTs", "FAIL", f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Get User NFTs", "FAIL", f"Exception: {str(e)}")

    def test_get_all_nfts(self):
        """Test GET /user_nft (list all user's NFTs)"""
        try:
            response = self.make_request("GET", "/user_nft")

            if response.status_code == 200:
                nfts = response.json()
                self.log_test("Get All NFTs", "PASS", f"Retrieved {len(nfts)} NFTs")
            else:
                self.log_test("Get All NFTs", "FAIL", f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Get All NFTs", "FAIL", f"Exception: {str(e)}")

    def test_update_user_nft(self):
        """Test PUT /user_nft/{id}"""
        if not self.created_nft_id:
            self.log_test("Update User NFT", "SKIP", "No NFT ID available")
            return

        try:
            update_data = {
                "user_id": self.user_id,
                "nft_collection": "BoredApeYachtClub",
                "nft_id": "1234",
                "used": True  # Mark as used
            }
            response = self.make_request("PUT", f"/user_nft/{self.created_nft_id}", data=update_data)

            if response.status_code == 200:
                updated_nft = response.json()
                self.log_test("Update User NFT", "PASS", f"Updated NFT, used: {updated_nft.get('used')}")
            else:
                self.log_test("Update User NFT", "FAIL", f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Update User NFT", "FAIL", f"Exception: {str(e)}")

    # ============= SOCIAL TESTS =============
    def test_create_user_social(self):
        """Test POST /user_social"""
        if not self.user_id:
            self.log_test("Create User Social", "SKIP", "No user_id available")
            return

        try:
            social_data = {
                "user_id": self.user_id,
                "platform": "twitter",
                "handle": f"test_user_{int(time.time())}"  # Unique handle
            }
            response = self.make_request("POST", "/user_social", data=social_data)

            if response.status_code == 201:
                created_social = response.json()
                self.created_social_id = created_social.get("id")
                self.log_test("Create User Social", "PASS", f"Created Social ID: {self.created_social_id}")
            else:
                self.log_test("Create User Social", "FAIL",
                              f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            self.log_test("Create User Social", "FAIL", f"Exception: {str(e)}")

    def test_get_user_socials(self):
        """Test GET /users/me/socials"""
        try:
            response = self.make_request("GET", "/users/me/socials")

            if response.status_code == 200:
                socials = response.json()
                self.log_test("Get User Socials", "PASS", f"Found {len(socials)} socials")
            else:
                self.log_test("Get User Socials", "FAIL", f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Get User Socials", "FAIL", f"Exception: {str(e)}")

    def test_check_social_handle(self):
        """Test GET /socials/check/{platform}/{handle}"""
        try:
            test_handle = f"test_check_{int(time.time())}"
            response = self.make_request("GET", f"/socials/check/twitter/{test_handle}")

            if response.status_code == 200:
                data = response.json()
                available = data.get("available")
                self.log_test("Check Social Handle", "PASS", f"Handle available: {available}")
            else:
                self.log_test("Check Social Handle", "FAIL", f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Check Social Handle", "FAIL", f"Exception: {str(e)}")

    # ============= WALLET CHECK TESTS =============
    def test_check_wallet_availability(self):
        """Test GET /users/check-wallet/{wallet_address}"""
        try:
            test_wallet = "0x1234567890123456789012345678901234567890"
            response = self.make_request("GET", f"/users/check-wallet/{test_wallet}")

            if response.status_code == 200:
                data = response.json()
                available = data.get("available")
                self.log_test("Check Wallet Availability", "PASS", f"Wallet available: {available}")
            else:
                self.log_test("Check Wallet Availability", "FAIL", f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Check Wallet Availability", "FAIL", f"Exception: {str(e)}")

    # ============= USER CRUD TESTS =============
    def test_get_users_list(self):
        """Test GET /users (list users)"""
        try:
            response = self.make_request("GET", "/users")

            if response.status_code == 200:
                users = response.json()
                self.log_test("Get Users List", "PASS", f"Retrieved {len(users)} users")
            else:
                self.log_test("Get Users List", "FAIL", f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Get Users List", "FAIL", f"Exception: {str(e)}")

    def test_get_user_by_id(self):
        """Test GET /users/{id}"""
        if not self.user_id:
            self.log_test("Get User By ID", "SKIP", "No user_id available")
            return

        try:
            response = self.make_request("GET", f"/users/{self.user_id}")

            if response.status_code == 200:
                user = response.json()
                self.log_test("Get User By ID", "PASS", f"Retrieved user: {user.get('wallet_address')}")
            else:
                self.log_test("Get User By ID", "FAIL", f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Get User By ID", "FAIL", f"Exception: {str(e)}")

    # ============= AUTHENTICATION VERIFICATION TESTS =============
    def test_unauthorized_access(self):
        """Test that endpoints require authentication"""
        try:
            # Test without auth header
            response = self.make_request("GET", "/users/me", use_auth=False)

            if response.status_code == 401:
                self.log_test("Unauthorized Access", "PASS", "Correctly rejected unauthenticated request")
            else:
                self.log_test("Unauthorized Access", "FAIL", f"Expected 401, got {response.status_code}")
        except Exception as e:
            self.log_test("Unauthorized Access", "FAIL", f"Exception: {str(e)}")

    def test_invalid_token(self):
        """Test with invalid JWT token"""
        try:
            invalid_headers = {
                "Authorization": "Bearer invalid_token_here",
                "Content-Type": "application/json"
            }
            response = self.make_request("GET", "/users/me", headers=invalid_headers, use_auth=False)

            if response.status_code == 401:
                self.log_test("Invalid Token", "PASS", "Correctly rejected invalid token")
            else:
                self.log_test("Invalid Token", "FAIL", f"Expected 401, got {response.status_code}")
        except Exception as e:
            self.log_test("Invalid Token", "FAIL", f"Exception: {str(e)}")

    # ============= CLEANUP TESTS =============
    def test_cleanup_created_data(self):
        """Clean up test data"""
        cleanup_results = []

        # Delete created NFT
        if self.created_nft_id:
            try:
                response = self.make_request("DELETE", f"/user_nft/{self.created_nft_id}")
                if response.status_code == 200:
                    cleanup_results.append("NFT deleted")
                else:
                    cleanup_results.append(f"NFT delete failed: {response.status_code}")
            except Exception as e:
                cleanup_results.append(f"NFT delete error: {str(e)}")

        # Delete created social
        if self.created_social_id:
            try:
                response = self.make_request("DELETE", f"/user_social/{self.created_social_id}")
                if response.status_code == 200:
                    cleanup_results.append("Social deleted")
                else:
                    cleanup_results.append(f"Social delete failed: {response.status_code}")
            except Exception as e:
                cleanup_results.append(f"Social delete error: {str(e)}")

        if cleanup_results:
            self.log_test("Cleanup", "PASS", "; ".join(cleanup_results))
        else:
            self.log_test("Cleanup", "SKIP", "No cleanup needed")

    # ============= MAIN TEST RUNNER =============
    def run_all_tests(self):
        """Run all tests in sequence"""
        print("=" * 60)
        print("🚀 Starting Hii Box API Test Suite")
        print("=" * 60)

        # Health and basic tests
        self.test_health_check()
        self.test_login_endpoint()

        # Authentication verification
        self.test_unauthorized_access()
        self.test_invalid_token()

        # User profile tests
        self.test_get_current_user()
        self.test_get_user_keys()
        self.test_get_campaign_status()

        # User CRUD tests
        self.test_get_users_list()
        self.test_get_user_by_id()

        # NFT tests
        self.test_create_user_nft()
        self.test_get_user_nfts()
        self.test_get_all_nfts()
        self.test_update_user_nft()

        # Social tests
        self.test_create_user_social()
        self.test_get_user_socials()
        self.test_check_social_handle()

        # Additional endpoint tests
        self.test_check_wallet_availability()

        # Cleanup
        self.test_cleanup_created_data()

        # Print summary
        self.print_test_summary()

    def print_test_summary(self):
        """Print test results summary"""
        print("\n" + "=" * 60)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 60)

        total_tests = len(self.test_results)
        passed = len([r for r in self.test_results if r["status"] == "PASS"])
        failed = len([r for r in self.test_results if r["status"] == "FAIL"])
        skipped = len([r for r in self.test_results if r["status"] == "SKIP"])

        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⏭️  Skipped: {skipped}")
        print(f"Success Rate: {(passed / total_tests) * 100:.1f}%" if total_tests > 0 else "0%")

        if failed > 0:
            print("\n🔍 FAILED TESTS:")
            for result in self.test_results:
                if result["status"] == "FAIL":
                    print(f"  ❌ {result['test']}: {result['details']}")

        print("\n" + "=" * 60)

        # Save results to file
        with open("test_results.json", "w") as f:
            json.dump(self.test_results, f, indent=2)
        print("📄 Detailed results saved to test_results.json")


def main():
    """Main function to run tests"""
    config = TestConfig()

    print(f"🎯 Testing API at: {config.BASE_URL}")
    print(f"🔑 Using wallet: {config.WALLET_ADDRESS}")
    print(f"⏱️  Token (first 20 chars): {config.ACCESS_TOKEN[:20]}...")

    tester = APITester(config)
    tester.run_all_tests()


if __name__ == "__main__":
    main()