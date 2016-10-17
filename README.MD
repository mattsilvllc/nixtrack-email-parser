### Nutritionix Track E-mail Parser
AWS Lambda function which parses incoming AWS SES e-mails and hits [Nutritionix Natural API](https://developer.nutritionix.com/docs/v2) endpoint passing the e-mail text body as query, then reply e-mail with a confirmation.

#### Installation
- Install Dependencies
```shell
pip install -r requirements.txt
```
- Rename or copy `config/production.json.example` to `config/production.json`
and populate with your credentials and preferences.

#### Build
This command will generate a file named lambda_src.zip
```shell
bash build.sh
```

#### Deployment
- [Upload](https://docs.aws.amazon.com/toolkit-for-eclipse/v1/user-guide/lambda-tutorial.html#id11) lambda_src.zip to AWS Lambda, set handler name as `main.hanlder`
- [Create AWS SES Rule Set](https://docs.aws.amazon.com/ses/latest/DeveloperGuide/receiving-email-receipt-rule-set.html)

#### Local Testing
```shell
python-lambda-local -l ./lib -f handler main.py event.json
```
