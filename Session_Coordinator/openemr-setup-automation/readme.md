# automation for openemr setup and api client creation
Uses selenium to automate the first time setup of openemr and the creation of an api client

Note that setup.py has seperate requirements from the rest of the project (noteably Selinium) so use of a seperate virtual environement is reccomended.

`python3 setup.py --help` for an explanation of every argument & it's role.

Defaults are specific to a dockerized environement with a database on the internal docker network network at 172.17.0.2 and an openemr pod at 172.17.0.3 with basic testing credentials. You will need to change this depending on your environement.

# usage
- `python3 setup.py`
 - pass args as needed
- a browser window should open and begin doing things. You should be able to do other things so long as you don't disturb the browser window
- wait about 5-10 minutes - the browser will close automatically when the script is finished
- the script will log the client_id and client_secret required to connect to openemr if everything goes well
 - data is the entire response from openemr's api client creation with extra metadata
 - you may see some exceptions logged, that's fine so long as the client id & secret is given at the end.
 - if the script fails at api client creation you will get a log asking to ensure setup worked & create + enable an api client manually
 - any fatal errors will result in an actual script crash with no client_id or secret given.