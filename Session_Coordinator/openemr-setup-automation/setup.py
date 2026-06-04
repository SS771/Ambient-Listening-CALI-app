from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
import requests
import argparse, json, time

def retryable(retries=1, wait=5): #decorator to auto retry functions that may fail due to network latency
    def fwrap(func):
        def wrapper(*args, **kwargs):
            _retries = 0
            while _retries <= retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    print(f"<exception try={_retries}>","\n",e,"\n<exception end>")
                    if wait > 0:
                        print(f"<exception wait start {time.time()}>")
                        time.sleep(wait)
                        print(f"<exception wait stop {time.time()}>")
                        if _retries == retries: #this was our last chance - crash
                            raise e
                finally:
                    _retries = _retries+1
                
        return wrapper
    return fwrap

def failable(default=None): #decorator for things that don't have to succeed
    def fwrap(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                print("<previous step failed - continuing>")
            return default
        return wrapper
    return fwrap

_ADMIN_IFRAME_NAME = 'adm' #config menu has options & navigation in an iframe with this name        

def setup(url):
    driver = webdriver.Firefox()
    #opts = webdriver.ChromeOptions()
    #opts.add_argument("--disable-notifications") #disable chrome's various password prompts
    driver.get(url)
    driver.implicitly_wait(3.0)
    return driver

def teardown(driver):
    driver.quit()

@retryable()
def click_button_with_text(driver, text):
    try:
        button = driver.find_element(By.XPATH, f"//button[contains(normalize-space(), '{text}')]")
        button.click()
    except Exception as e:
        print(f"Could not find or click button with text '{text}'", "\nException:", e)

def fill_out_setup_form(driver, mysqlHost, mysqlUserPass, mysqlRootPass, openemrHost, initialAdminUsername, initialAdminPassword):
    # MySQL host ip
    server = driver.find_element(By.ID, "server")
    server.clear()
    server.send_keys(mysqlHost)

    # MySQL Password
    password = driver.find_element(By.ID, "pass")
    password.clear()
    password.send_keys(mysqlUserPass)

    # MySQL Root Password
    root_password = driver.find_element(By.ID, "rootpass")
    root_password.clear()
    root_password.send_keys(mysqlRootPass)

    # OpenEMR host ip
    loginhost = driver.find_element(By.ID, "loginhost")
    loginhost.clear()
    loginhost.send_keys(openemrHost)

    # Initial User
    initial_user_login = driver.find_element(By.ID, "iuser")
    initial_user_login.clear()
    initial_user_login.send_keys(initialAdminUsername)

    # Initial User Pass
    initial_user_pass = driver.find_element(By.ID, "iuserpass")
    initial_user_pass.clear()
    initial_user_pass.send_keys(initialAdminPassword)
    
    # submit
    create_db_button = driver.find_element(By.ID, "create_db_button")
    create_db_button.click() #FIXME - this ok?
    '''
    try:
        create_db_button.click()
    except:
        #above click seemingly never registers as done bc of how the page redirects
        #if longer than 120s to get to db finished page error is raised - which we ignore here
        print("!!! create db button exception still happens") #FIXME
        #pass
    '''
def wait_for_setup_finished(driver):
    html = driver.page_source
    print("begin wait for page source", time.time())
    ndx = 0
    t = 30
    def getBtn():
        try:
            return driver.find_element(By.ID, "step-4-btn")
        except:
            return None
    continue_button = getBtn()
    while continue_button == None:
        ndx = ndx+1
        print(f"SLEEPING : {t*ndx}")
        time.sleep(t)
        html = driver.page_source
        if ("ERROR" in html):
            print("ERROR OCCURED")
            exit()
        continue_button = getBtn()
    print("DONE SLEEPING", time.time())
    continue_button.click()

def select_theme(driver):
    checkbox = driver.find_element(By.XPATH, "//input[@type='checkbox' and @value='keep_current']")
    checkbox.click()
    click_button_with_text(driver, "Proceed to Final Step")

def get_to_login_screen(driver):
    #start_button isn't a button it's a '<a>'
    start_button = driver.find_element(By.XPATH, "//a[contains(normalize-space(), 'Start')]")
    start_button.click()

@retryable()
def login_to_openemr(driver, username, password):
    username_field = driver.find_element(By.ID, "authUser")
    password_field = driver.find_element(By.ID, "clearPass")
    login_button = driver.find_element(By.ID, "login-button")
    username_field.clear()
    password_field.clear()
    username_field.send_keys(username)
    password_field.send_keys(password)
    login_button.click()

@failable()
def handle_telemetry_popup(driver):
    telemetry_checkbox = driver.find_element(By.ID, "allowTelemetry")
    telemetry_checkbox.click()
    click_button_with_text(driver, "Submit")

@retryable()
def header_nav_to_config(driver):
    admin_dropdown = driver.find_element(By.XPATH, "//div[contains(normalize-space(), 'Admin') and @role='button']")
    ActionChains(
        driver
    ).move_to_element(
        admin_dropdown
    ).move_by_offset( #https://www.selenium.dev/documentation/webdriver/actions_api/mouse/ - first argument X specifies to move right when positive, while the second argument Y specifies to move down when positive. So moveByOffset(30, -10) moves right 30 and up 10
        0
        ,admin_dropdown.size['height']+1 # trying to get the "Config" item with queries didn't work, so we just move the mouse down a bit & click
    ).click().perform()

@retryable()
def turn_on_webapi(driver):
    iframe = driver.find_element(By.NAME, _ADMIN_IFRAME_NAME)
    driver.switch_to.frame(iframe)
    try:
        connector_button = driver.find_element(By.XPATH, "//a[contains(text(), 'Connectors')]")
        time.sleep(1.0) #page needs to finish loading before we scroll or it snaps to the top
        driver.execute_script("arguments[0].scrollIntoView(true);", connector_button)
        ActionChains(driver).move_to_element(connector_button).click().perform()

        time.sleep(2.0)
        fhir_api_chkbx = driver.find_element(By.ID, "form_374")
        fhir_api_chkbx.click()

        std_api_chkbx = driver.find_element(By.ID, "form_376")
        std_api_chkbx.click()

        pw_grant = Select(driver.find_element(By.ID, "form_378"))
        pw_grant.select_by_visible_text("On for Users Role")

        save_button = driver.find_element(By.XPATH, "//button[@name='form_save' and @value='Save']")
        save_button.click()
    except Exception as e:
        driver.switch_to.default_content()
        raise e #trigger retry
    driver.switch_to.default_content()

@failable()
def create_webclient(url, redirect_uri):
    _url = f"{url}oauth2/default/registration"
    headers = {'Content-Type': 'application/json'}
    data = {
        "application_type": "private",
        "redirect_uris": [
            redirect_uri
        ],
        "post_logout_redirect_uris": [
            "https://client.example.org/logout/callback"
        ],
        "client_name": "Full Access API Client",
        "token_endpoint_auth_method": "client_secret_post",
        "contacts": [
            "me@example.org",
            "them@example.org"
        ],
        "scope": "openid offline_access api:oemr api:fhir api:port user/allergy.read user/allergy.write user/appointment.read user/appointment.write user/dental_issue.read user/dental_issue.write user/document.read user/document.write user/drug.read user/encounter.read user/encounter.write user/facility.read user/facility.write user/immunization.read user/insurance.read user/insurance.write user/insurance_company.read user/insurance_company.write user/insurance_type.read user/list.read user/medical_problem.read user/medical_problem.write user/medication.read user/medication.write user/message.write user/patient.read user/patient.write user/practitioner.read user/practitioner.write user/prescription.read user/procedure.read user/soap_note.read user/soap_note.write user/surgery.read user/surgery.write user/transaction.read user/transaction.write user/vital.read user/vital.write user/AllergyIntolerance.read user/CareTeam.read user/Condition.read user/Coverage.read user/Encounter.read user/Immunization.read user/Location.read user/Medication.read user/MedicationRequest.read user/Observation.read user/Organization.read user/Organization.write user/Patient.read user/Patient.write user/Practitioner.read user/Practitioner.write user/PractitionerRole.read user/Procedure.read patient/AllergyIntolerance.read patient/CareTeam.read patient/Condition.read patient/Coverage.read patient/Encounter.read patient/Immunization.read patient/MedicationRequest.read patient/Observation.read patient/Patient.read patient/Procedure.read"
    }
    response = requests.post(_url, headers=headers, data=json.dumps(data), verify=False)
    try:
        return response.json()
    except requests.exceptions.JSONDecodeError as e:
        print("Couldn't parse json for create webclient response","\n", f"Status:{response.status_code}", "\n", f"Text>> {response.text}")
        raise e

@retryable()
def header_nav_to_apiclients(driver):
    admin_dropdown = driver.find_element(By.XPATH, "//div[contains(normalize-space(), 'Admin') and @role='button']")
    admin_dropdown_parent = admin_dropdown.find_element(By.XPATH, ".//..")
    ActionChains(
        driver
    ).move_to_element(
        admin_dropdown
    ).move_to_element(
        admin_dropdown_parent.find_element(By.XPATH, "//div[contains(text(), 'System')]")
    ).move_to_element(
        admin_dropdown_parent.find_element(By.XPATH, "//div[contains(text(), 'Backup')]")
    ).move_to_element(
        admin_dropdown_parent.find_element(By.XPATH, "//div[contains(text(), 'API Clients')]")
    ).click().perform()

@retryable()
def enable_single_apiclient(driver):
    iframe = driver.find_element(By.NAME, _ADMIN_IFRAME_NAME)
    driver.switch_to.frame(iframe)
    
    try:
        edit_btn = driver.find_element(By.XPATH, "//a[contains(text(), 'Edit')]")
        edit_btn.click()

        enable_btn = driver.find_element(By.XPATH, "//a[contains(text(), 'Enable Client')]")
        enable_btn.click()
    except Exception as e:
        driver.switch_to.default_content()
        raise e #trigger retry
    driver.switch_to.default_content()


def print_page_html(driver):
    try:
        html = driver.page_source
        print(html)
    except Exception as e:
        print("Could not retrieve page HTML:", e)

def runOpenemrSetup(
        openemrURL = "http://localhost:8080/" #needs the '/' at the end
        , mysqlHost = "172.17.0.2" #database IP (for local env - started 1st)
        , mysqlUserPass = "password" #for created mysql user
        , mysqlRootPass = "password" #existing mysql root pass to create above mysql user
        , openemrHost = "172.17.0.3" #openemr ip (for local env - started 2nd)
        , initialAdminUsername = "openemr-admin" #initial openemr login creds to create
        , initialAdminPassword = "openemr-admin"
        , redirectURI = "http://0.0.0.0:5000/oauth2/default"
    ):
    driver = setup(openemrURL)
    title = driver.title
    print(title)
    try:
        # step 0
        click_button_with_text(driver, "Proceed to Step 1")
        print("step 0 done")
        # step 1
        click_button_with_text(driver, "Proceed to Step 2")
        print("step 1 done")
        # step 2 - fill out variables
        fill_out_setup_form(driver, mysqlHost, mysqlUserPass, mysqlRootPass, openemrHost, initialAdminUsername, initialAdminPassword)
        print("step 2 done")
        # step 3 - wait for db setup to finish then click button
        wait_for_setup_finished(driver)
        print("step 3 done")
        # step 4 - php config notes
        click_button_with_text(driver, "Proceed to Step 5")
        print("step 4 done")
        # step 5 - apache notes
        click_button_with_text(driver, "Proceed to Select a Theme")
        print("step 5 done")
        # step 6 - select theme
        #driver.find_element(By.CSS_SELECTOR, "input.check[value='keep_current']")
        select_theme(driver)
        print("step 6 done")
        #setup is done - click start
        get_to_login_screen(driver)
        print("at login screen")
        
        # login
        login_to_openemr(driver, initialAdminUsername, initialAdminPassword)
        print("login done")
        # dismiss the ehr telemetry popup
        handle_telemetry_popup(driver)
        print("telemetry options set")
        #go to admin>config
        time.sleep(2.0)
        header_nav_to_config(driver)
        print("at config page")
        #go to connectors, click api checkboxes and submit
        time.sleep(5.0) #config page takes a few seconds to load
        turn_on_webapi(driver)
        print("webapi enabled")
        #send request to make api client
        webclient_response = create_webclient(openemrURL, redirectURI)
        if webclient_response == None:
            print("Unable to create webclient. If setup worked to this point ensure the apis are turned on, then create & enable an apiclient manually")
            teardown(driver)
            exit()
        print("created webclient")
        #go to screen to turn on api client
        header_nav_to_apiclients(driver)
        time.sleep(5.0) # wait for the page to load
        #enable the api client
        enable_single_apiclient(driver)
        print("enabled webclient")
        #print the api client details (so we can copy+paste to session coordinator)
        print(webclient_response)
        #print_page_html(driver)
    except Exception as e:
        print("<runOpenemrSetup FAILURE>")
    teardown(driver)

def genArgs(parser = argparse.ArgumentParser(description = "Automatically configures an openemr instance via browser automation with Selinium")):
    parser.add_argument("--openemr_url", "-o_u", default="http://localhost:8080/", help = "url to the EMR instance, ends with '/', used as the browser navigation location & api host (public address)")
    parser.add_argument("--mysql_host", "-m_h", default="172.17.0.2", help = "database IP address, should be relative to openemr pod (internally routed address)")
    parser.add_argument("--mysql_user_pass", "-m_up", default="password", help = "password for newly created mysql user that openemr will use")
    parser.add_argument("--mysql_root_pass", "-m_rp", default="password", help = "existing root password for the mysql database, used for setup")
    parser.add_argument("--openemr_host", "-o_h", default = "172.17.0.3", help = "openemr IP address, should be relative to the database as it's assigned to the created db user openemr will use (interally routed address)")
    parser.add_argument("--initial_admin_username", "-a_u", default = "openemr-admin", help = "username for the initial created administrator user created")
    parser.add_argument("--initial_admin_password", "-a_p", default = "openemr-admin", help = "password for the initial created administrator account")
    parser.add_argument("--openemr_redirect_uri", "-o_ru", default="http://0.0.0.0:5000/oauth2/default", help = "redirect URI for oauth login to openemr")
    return parser

if __name__ == "__main__":
    args = genArgs().parse_args()
    runOpenemrSetup(
        openemrURL = args.openemr_url
        , mysqlHost = args.mysql_host
        , mysqlUserPass = args.mysql_user_pass
        , mysqlRootPass = args.mysql_root_pass
        , openemrHost = args.openemr_host
        , initialAdminUsername = args.initial_admin_username
        , initialAdminPassword = args.initial_admin_password
        , redirectURI=args.openemr_redirect_uri
    )
    