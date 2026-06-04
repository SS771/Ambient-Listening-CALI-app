
# Environment variables
* jwt_secret_key = <random string; try cmd : `openssl rand -hex 32`>
* captioning_apikey = apikey client should caption with
* auth_password = global pw to get through the /auth endpoint
* wlc_captions_host = captions host url - default `wss://live-captioning-wlc-staging.watsonmedia.ibm.com/speech-to-text/api/v2/recognize?model_id=fea68eb4-4a08-415a-a7d1-ec3080235fdb`
  * ensure using ws url when connecting to local cluster that isn't SSL ex `ws://live-captioning.default.svc.cluster.local:3002/speech-to-text/api/v2/recognize?model_id=fea68eb4-4a08-415a-a7d1-ec3080235fdb`
* wlc_auth_url = auth url host, default of `https://api-wlc-staging.watsonmedia.ibm.com/authorization/api/v1/token`
  * ensure using an http url when connecting to internal services ex `http://authorization-api:6400/authorization/api/v1/token`
* allowed_users = comma seperated values of allowed users with no spaces or formatting, ex : alpha@fakedomain.com,Example McUsername,omega@fakedomain.com
* openemr_client_id = ID of an API client that is set up in an openemr instance. 
  * IF THIS VAR IS NOT SET OR SET TO "", OpenEMR interactions are short-circuited to ease local development
* domain_term_url = URL for the domain term system, to support client flow of adding domain terms
  ## removed for current password auth flow - use the EMR's credentials instead to login to the app:
    * openemr_username = username that is set up in an openemr instance, used to allow the session coordinator to authenticate with openemr
    * openemr_password = password that is set up for above username, used to allow the session coordinator to authenticate with openemr
* agent_database_dir = is `content/chr` by default, dir with chroma DB of documents for use with agents
* verbose_output = <truthy or falsey value> if `bool(verbose_output) === True` enable extra debug logging, else is disabled
* openemr_host = host URL for openemr container, default to localhost for testing
* auth_redirect_uri = redirect URL for after authentication (oauth), default to localhost for testing

# Local exports as an example
* export jwt_secret_key='0b20ffd253ad3d7b37e1233db2789701c4f073dd13de61bc0018a4b540dcbb50'
* export captioning_apikey='c-p6c0uKtizNbe9m2ytRp4sicpoBMcbJ'
* export openemr_client_id='<you'll have this value after you go through the setup readme>'
* export openemr_client_secret='<you'll have this after you go through the setup readme>'
* export openemr_host = http://localhost:8080/
* export auth_redirect_uri = http://0.0.0.0:5000/oauth2/default
  ## removed for current password auth flow - use the EMR's credentials instead to login to the app:
    * export allowed_users='caseyhetzler@ibm.com,brendon.lebaron@ibm.com,rishi.bakshi@ibm.com'
    * export auth_password='watson2025'
    * export openemr_username='openemr-local-admin'
    * export openemr_password='openemr-local-admin'

# wavelength zone env variables as an example
```- env:
  - name: jwt_secret_key
  value: 0b20ffd253ad3d7b37e1233db2789701c4f073dd13de61bc0018a4b540dcbb50
  - name: auth_password
  value: watson2025
  - name: allowed_users
  value: caseyhetzler@ibm.com,brendon.lebaron@ibm.com,rishi.bakshi@ibm.com
  - name: captioning_apikey
  value: c-p6c0uKtizNbe9m2ytRp4sicpoBMcbJ
  - name: wlc_captions_host
  value: ws://live-captioning.default.svc.cluster.local:3002/speech-to-text/api/v2/recognize?model_id=fea68eb4-4a08-415a-a7d1-ec3080235fdb
  - name: wlc_auth_url
  value: http://authorization-api:6400/authorization/api/v1/token
  - name: openemr_client_id
  value: '<you'll have this value after you go through the setup readme>'
  - name: openemr_client_secret
  value: '<you'll have this after you go through the setup readme>'
  - name: openemr_host
  value: http://openemr.default.svc.cluster.local:80/
  - name: redirect_uri
  value: https://session-cordination-wlc-atlanta.watsonmedia.ibm.com/oauth2/default
  - name: openemr_host
  value: http://openemr.default.svc.cluster.local:80/
  - name: auth_redirect_uri
  value: https://session-cordination-wlc-atlanta.watsonmedia.ibm.com/oauth2/default
  ```

# Differences in wavelength
* wlc_auth_url and wlc_captions_host should be exported
  * host for services should be set to kubernetes service name + port, e.g. `live-captioning.default.svc.cluster.local:3002`


# Running unit tests
* Run the live unit tests that connect to the prompt engine with `python3 -m unittest test_transcript_to_real_prompt_results.py`
  * for verbose output use `python3 -m unittest -v test_transcript_to_real_prompt_results.py`
* run basic logic tests with `python3 -m unittest openemr/connector_tests.py`
* To run endpoint specific tests (as have been added for `app/ai.py`) from the repo root run `python3 -m unittest app/ai.py`
  * you can use multiple files in one unittest call ex: `python3 -m unittest app/ai.py app/middleware/wlc_auth.py openemr/connector_tests.py`
running `python3 -m unittest` should find and run all the tests in the project but on my local it only ran the ones in the test/ folder
* Run with coverage: 
  * first install coverage `pip3 install coverage`
  * run with `coverage run test_coordinationlayer.py`
  * generate html report using `coverage html`
  * `cd htmlcov`
  * `ls` then open `class_index.html` in your browser to see a coverage report

# Build & run a local container
* Build - replace X.Y.Z with version: `docker build -t us.icr.io/watsonmedia-wlc/session-coordinator-al:<X.Y.Z> .`
* Run - replace X.Y.Z with version: `docker run -p 5000:5000 -e watsonx_apikey -e watsonx_project_id -e jwt_secret_key -e captioning_apikey -e openemr_client_id -e openemr_client_secret -e openemr_host='http://172.17.0.3/' us.icr.io/watsonmedia-wlc/session-coordinator-al:<X.Y.Z>`
  * you must export values for: `watsonx_apikey, watsonx_project_id, jwt_secret_key, captioning_apikey, openemr_client_id, openemr_client_secret` or define them in the command
  * replace `openemr_host='...'` with whatever the internal (docker given) IP of the openemr pod is, or other ingress to an openemr instance

# Set up a local OpenEMR pod
* Please see openemr_from_scratch_dev_setup.txt for detailed instructions
