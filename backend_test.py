import requests
import sys
import json
import os
from datetime import datetime

class LandFallAPITester:
    def __init__(self, base_url=None):
        if base_url is None:
            base_url = os.environ.get("LANDFALL_API_BASE_URL", "http://localhost:8001")
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.token = None
        self.user_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name} - PASSED")
        else:
            print(f"❌ {name} - FAILED: {details}")
        
        self.test_results.append({
            "test": name,
            "success": success,
            "details": details
        })

    def run_test(self, name, method, endpoint, expected_status, data=None, auth_required=True):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        if auth_required and self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)

            success = response.status_code == expected_status
            
            if success:
                self.log_test(name, True)
                try:
                    return True, response.json()
                except:
                    return True, response.text
            else:
                error_msg = f"Expected {expected_status}, got {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f" - {error_detail}"
                except:
                    error_msg += f" - {response.text[:200]}"
                
                self.log_test(name, False, error_msg)
                return False, {}

        except Exception as e:
            self.log_test(name, False, f"Request error: {str(e)}")
            return False, {}

    def test_health_check(self):
        """Test API health check"""
        return self.run_test("Health Check", "GET", "", 200, auth_required=False)

    def test_register(self, email, password):
        """Test user registration"""
        success, response = self.run_test(
            "User Registration",
            "POST",
            "auth/register",
            200,
            data={"email": email, "password": password, "role": "player"},
            auth_required=False
        )
        
        if success and 'token' in response:
            self.token = response['token']
            self.user_id = response['user']['id']
            print(f"   Token obtained: {self.token[:20]}...")
            return True
        return False

    def test_login(self, email, password):
        """Test user login"""
        success, response = self.run_test(
            "User Login",
            "POST",
            "auth/login",
            200,
            data={"email": email, "password": password},
            auth_required=False
        )
        
        if success and 'token' in response:
            self.token = response['token']
            self.user_id = response['user']['id']
            print(f"   Token obtained: {self.token[:20]}...")
            return True
        return False

    def test_get_me(self):
        """Test get current user"""
        success, response = self.run_test("Get Current User", "GET", "auth/me", 200)
        return success and 'email' in response

    def test_create_deck(self, name):
        """Test deck creation"""
        success, response = self.run_test(
            "Create Deck",
            "POST",
            "decks",
            200,
            data={"name": name, "commander": None}
        )
        
        if success and 'id' in response:
            return response['id']
        return None

    def test_get_decks(self):
        """Test get user decks"""
        success, response = self.run_test("Get User Decks", "GET", "decks", 200)
        return success, response

    def test_import_deck(self, deck_id, test_url):
        """Test deck import from URL"""
        success, response = self.run_test(
            "Import Deck from URL",
            "POST",
            f"decks/{deck_id}/import",
            200,
            data={"source_type": "url", "source_data": test_url}
        )
        
        if success and 'cards_count' in response:
            print(f"   Imported {response['cards_count']} cards")
            return response['cards_count']
        return 0

    def test_get_deck(self, deck_id):
        """Test get specific deck"""
        success, response = self.run_test("Get Deck Details", "GET", f"decks/{deck_id}", 200)
        
        if success:
            cards_count = len(response.get('cards', []))
            print(f"   Deck has {cards_count} cards")
            return success, cards_count
        return False, 0

    def test_analyze_deck(self, deck_id, categories=None):
        """Test deck analysis with optional categories"""
        data = {}
        if categories:
            data['categories'] = categories
            
        success, response = self.run_test(
            "Analyze Deck" + (f" (Categories: {categories})" if categories else ""),
            "POST",
            f"decks/{deck_id}/analyze",
            200,
            data=data
        )
        
        if success:
            adds_count = len(response.get('suggestions_add', []))
            cuts_count = len(response.get('suggestions_cut', []))
            print(f"   Analysis: {adds_count} adds, {cuts_count} cuts")
            return response.get('id'), adds_count, cuts_count
        return None, 0, 0

    def test_get_analysis(self, analysis_id):
        """Test get analysis results and verify enhanced features"""
        success, response = self.run_test("Get Analysis Results", "GET", f"analysis/{analysis_id}", 200)
        
        if success:
            # Check for enhanced features
            enhanced_features = {
                'playstyle_tips': response.get('playstyle_tips', []),
                'detected_themes': response.get('detected_themes', []),
                'combo_suggestions': response.get('combo_suggestions', []),
                'commander_synergies': response.get('commander_synergies', [])
            }
            
            print(f"   Enhanced Features:")
            print(f"     - Playstyle Tips: {len(enhanced_features['playstyle_tips'])}")
            print(f"     - Detected Themes: {len(enhanced_features['detected_themes'])}")
            print(f"     - Combo Suggestions: {len(enhanced_features['combo_suggestions'])}")
            print(f"     - Commander Synergies: {len(enhanced_features['commander_synergies'])}")
            
            # Check if suggestions have image URLs
            adds = response.get('suggestions_add', [])
            cuts = response.get('suggestions_cut', [])
            
            adds_with_images = sum(1 for add in adds if add.get('image_url'))
            cuts_with_images = sum(1 for cut in cuts if cut.get('image_url'))
            
            print(f"     - Adds with images: {adds_with_images}/{len(adds)}")
            print(f"     - Cuts with images: {cuts_with_images}/{len(cuts)}")
            
            return success, response, enhanced_features
        return False, {}, {}

    def test_export_analysis(self, analysis_id):
        """Test export analysis to markdown"""
        success, response = self.run_test("Export Analysis", "GET", f"analysis/{analysis_id}/export", 200)
        
        if success and 'markdown' in response:
            print(f"   Export filename: {response.get('filename', 'N/A')}")
            return True
        return False

    def test_delete_deck(self, deck_id):
        """Test deck deletion"""
        success, response = self.run_test("Delete Deck", "DELETE", f"decks/{deck_id}", 200)
        return success

    def test_commander_lookup(self, commander_name):
        """Test commander lookup functionality"""
        success, response = self.run_test(
            f"Commander Lookup ({commander_name})",
            "POST",
            "commander/lookup",
            200,
            data={"commander_name": commander_name}
        )
        
        if success:
            required_fields = ['name', 'strategy_tips', 'synergies', 'suggested_cards', 'combos', 'image_url']
            missing_fields = [field for field in required_fields if field not in response]
            
            if missing_fields:
                print(f"   ⚠️  Missing fields: {missing_fields}")
            
            print(f"   Commander: {response.get('name', 'N/A')}")
            print(f"   Strategy Tips: {len(response.get('strategy_tips', []))}")
            print(f"   Synergies: {len(response.get('synergies', []))}")
            print(f"   Suggested Cards: {len(response.get('suggested_cards', []))}")
            print(f"   Combos: {len(response.get('combos', []))}")
            print(f"   Has Image: {'Yes' if response.get('image_url') else 'No'}")
            
            return success, response
        return False, {}

    def test_random_commander(self):
        """Test random commander generation"""
        success, response = self.run_test(
            "Random Commander",
            "POST",
            "commander/random",
            200,
            data={}
        )
        
        if success:
            print(f"   Random Commander: {response.get('name', 'N/A')}")
            print(f"   Strategy Tips: {len(response.get('strategy_tips', []))}")
            print(f"   Has Image: {'Yes' if response.get('image_url') else 'No'}")
            
            return success, response
        return False, {}

def main():
    print("🚀 Starting LandFall AI Backend API Tests")
    print("=" * 60)
    
    tester = LandFallAPITester()
    test_email = f"test_{datetime.now().strftime('%H%M%S')}@example.com"
    test_password = "TestPass123!"
    test_deck_name = f"Test Deck {datetime.now().strftime('%H:%M:%S')}"
    test_url = "https://archidekt.com/decks/16778041/enchant_suite"
    
    # Test sequence
    print(f"\n📧 Test user: {test_email}")
    print(f"🔗 Test URL: {test_url}")
    
    # 1. Health check
    if not tester.test_health_check()[0]:
        print("❌ API is not responding, stopping tests")
        return 1

    # 2. User registration
    if not tester.test_register(test_email, test_password):
        print("❌ Registration failed, stopping tests")
        return 1

    # 3. Get current user
    if not tester.test_get_me():
        print("❌ Get user failed, stopping tests")
        return 1

    # 4. Create deck
    deck_id = tester.test_create_deck(test_deck_name)
    if not deck_id:
        print("❌ Deck creation failed, stopping tests")
        return 1

    # 5. Get decks list
    success, decks = tester.test_get_decks()
    if not success:
        print("❌ Get decks failed")
        return 1

    # 6. Import deck from URL
    cards_imported = tester.test_import_deck(deck_id, test_url)
    if cards_imported == 0:
        print("❌ Deck import failed, stopping tests")
        return 1

    # 7. Verify deck has cards
    success, cards_count = tester.test_get_deck(deck_id)
    if not success or cards_count == 0:
        print("❌ Deck verification failed")
        return 1

    # Check if we have expected 71 cards
    if cards_count != 71:
        print(f"⚠️  Expected 71 cards, got {cards_count}")

    # 8. Test category-based analysis
    print("\n🎯 Testing Enhanced Analysis Features...")
    categories = ['draw', 'ramp']
    analysis_id_cat, adds_count_cat, cuts_count_cat = tester.test_analyze_deck(deck_id, categories)
    if not analysis_id_cat:
        print("❌ Category-based analysis failed")
        return 1

    # 9. Test full analysis (no categories)
    analysis_id, adds_count, cuts_count = tester.test_analyze_deck(deck_id)
    if not analysis_id:
        print("❌ Full deck analysis failed, stopping tests")
        return 1

    # 10. Get analysis results and verify enhanced features
    success, analysis_data, enhanced_features = tester.test_get_analysis(analysis_id)
    if not success:
        print("❌ Get analysis failed")
        return 1
    
    # Verify enhanced features are present
    if not enhanced_features['playstyle_tips']:
        print("⚠️  No playstyle tips found")
    if not enhanced_features['detected_themes']:
        print("⚠️  No detected themes found")
    if not enhanced_features['combo_suggestions']:
        print("⚠️  No combo suggestions found")

    # 11. Export analysis
    if not tester.test_export_analysis(analysis_id):
        print("❌ Export analysis failed")
        return 1

    # 12. Test Commander Lookup
    print("\n🔍 Testing Commander Lookup...")
    success, commander_data = tester.test_commander_lookup("Zur the Enchanter")
    if not success:
        print("❌ Commander lookup failed")
        return 1

    # 13. Test Random Commander
    print("\n🎲 Testing Random Commander...")
    success, random_commander = tester.test_random_commander()
    if not success:
        print("❌ Random commander failed")
        return 1

    # 14. Clean up - delete deck
    if not tester.test_delete_deck(deck_id):
        print("❌ Deck deletion failed")

    # Print final results
    print("\n" + "=" * 60)
    print(f"📊 FINAL RESULTS: {tester.tests_passed}/{tester.tests_run} tests passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 ALL TESTS PASSED!")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print("\nFailed tests:")
        for result in tester.test_results:
            if not result['success']:
                print(f"  - {result['test']}: {result['details']}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
