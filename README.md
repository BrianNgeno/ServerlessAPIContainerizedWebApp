# AWS Containerized Web App, Serverless API & CloudWatch Observability

This project demonstrates how to deploy a simple web application using **Amazon ECS with AWS Fargate**, build and store a Docker image in **Amazon ECR**, create a **serverless API using AWS Lambda and API Gateway**, and monitor the application using **Amazon CloudWatch**.

---

## Architecture

The solution consists of three main components:

```text
                         ┌─────────────────────┐
                         │       User          │
                         └──────────┬──────────┘
                                    │
                       ┌────────────▼────────────┐
                       │   ECS Fargate Web App   │
                       │                         │
                       │   Docker Container      │
                       └─────────────────────────┘


                         ┌─────────────────────┐
                         │       Client        │
                         └──────────┬──────────┘
                                    │
                              POST /submit
                                    │
                         ┌──────────▼──────────┐
                         │    API Gateway      │
                         │     REST API        │
                         └──────────┬──────────┘
                                    │
                         ┌──────────▼──────────┐
                         │       Lambda        │
                         │   Serverless API    │
                         └──────────┬──────────┘
                                    │
                         ┌──────────▼──────────┐
                         │     CloudWatch      │
                         │   Logs & Metrics    │
                         └─────────────────────┘
```

---

# Prerequisites

Before starting, ensure you have:

- An AWS account
- AWS CLI installed and configured
- Docker installed
- Git installed
- An IAM user or role with appropriate permissions
- Access to:
  - Amazon ECR
  - Amazon ECS
  - AWS Fargate
  - AWS Lambda
  - Amazon API Gateway
  - Amazon CloudWatch
  - AWS CloudFormation

Verify AWS CLI access:

```bash
aws sts get-caller-identity
```

---

# Step 1: Containerized Web Application

## 1.1 Create the Web Application

Create a simple static website.

Example project structure:

```text
container-app/
├── index.html
├── Dockerfile
└── README.md
```

Example `index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AWS ECS Application</title>
</head>

<body>
    <h1>Hello from AWS ECS Fargate!</h1>
    <p>This application is running inside a Docker container.</p>
</body>
</html>
```

---

## 1.2 Create the Dockerfile

Create a file named:

```text
Dockerfile
```

Add:

```dockerfile
FROM nginx:alpine

COPY index.html /usr/share/nginx/html/index.html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

This uses Nginx to serve the static website.

---

## 1.3 Build the Docker Image

From the project directory:

```bash
docker build -t aws-ecs-web-app .
```

Verify the image:

```bash
docker images
```

You should see:

```text
aws-ecs-web-app
```

---

# 1.4 Create an Amazon ECR Repository

Create an ECR repository:

```bash
aws ecr create-repository \
    --repository-name aws-ecs-web-app \
    --region us-east-1
```

Get your AWS account ID:

```bash
aws sts get-caller-identity --query Account --output text
```

Set your variables:

```bash
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPOSITORY=aws-ecs-web-app
```

---

## 1.5 Authenticate Docker with ECR

Run:

```bash
aws ecr get-login-password --region $AWS_REGION | \
docker login \
--username AWS \
--password-stdin \
$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
```

You should receive:

```text
Login Succeeded
```

---

## 1.6 Tag the Docker Image

```bash
docker tag aws-ecs-web-app:latest \
$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:latest
```

---

## 1.7 Push the Image to ECR

```bash
docker push \
$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:latest
```

Verify the image:

```bash
aws ecr list-images \
--repository-name $ECR_REPOSITORY \
--region $AWS_REGION
```

---

# 1.8 Deploy ECS Using CloudFormation

Create:

```text
ecs-cloudformation.yaml
```

The CloudFormation template should provision:

- ECS Cluster
- ECS Task Definition
- ECS Fargate Service
- Networking
- Security Group
- Load Balancer
- IAM execution role

Example simplified CloudFormation structure:

```yaml
AWSTemplateFormatVersion: '2010-09-09'

Description: ECS Fargate Web Application

Resources:

  ECSCluster:
    Type: AWS::ECS::Cluster
    Properties:
      ClusterName: aws-ecs-web-cluster

  TaskDefinition:
    Type: AWS::ECS::TaskDefinition
    Properties:
      Family: aws-ecs-web-task
      NetworkMode: awsvpc
      RequiresCompatibilities:
        - FARGATE
      Cpu: '256'
      Memory: '512'

      ExecutionRoleArn: !GetAtt ECSTaskExecutionRole.Arn

      ContainerDefinitions:
        - Name: web
          Image: YOUR_ECR_IMAGE_URI
          Essential: true

          PortMappings:
            - ContainerPort: 80
              Protocol: tcp

  ECSTaskExecutionRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: '2012-10-17'

        Statement:
          - Effect: Allow
            Principal:
              Service:
                - ecs-tasks.amazonaws.com

            Action:
              - sts:AssumeRole

      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
```

> **Note:** A production-ready ECS deployment should also include a VPC, subnets, security groups, Application Load Balancer, target group, and ECS service.

---

## 1.9 Deploy the CloudFormation Stack

Run:

```bash
aws cloudformation deploy \
    --template-file ecs-cloudformation.yaml \
    --stack-name aws-ecs-web-stack \
    --capabilities CAPABILITY_IAM \
    --region us-east-1
```

Check the stack:

```bash
aws cloudformation describe-stacks \
    --stack-name aws-ecs-web-stack \
    --region us-east-1
```

Once deployed, access the ECS application through the Load Balancer URL.

---

# Step 2: Serverless API

## 2.1 Create the Lambda Function

Create:

```text
lambda_function.py
```

Use:

```python
import json
import secrets
import string


def lambda_handler(event, context):

    # Log incoming request
    print("Received data:", event.get("body"))

    # Generate random submission ID
    characters = string.ascii_lowercase + string.digits

    submission_id = ''.join(
        secrets.choice(characters)
        for _ in range(8)
    )

    return {
        "statusCode": 200,

        "headers": {
            "Content-Type": "application/json"
        },

        "body": json.dumps({
            "message": "Data successfully received and logged!",
            "id": submission_id
        })
    }
```

The `print()` statement is automatically sent to **Amazon CloudWatch Logs** by AWS Lambda.

---

## 2.2 Create the Lambda Function

Create a deployment ZIP:

```bash
zip function.zip lambda_function.py
```

Create the Lambda function:

```bash
aws lambda create-function \
    --function-name submission-receiver \
    --runtime python3.12 \
    --handler lambda_function.lambda_handler \
    --zip-file fileb://function.zip \
    --role arn:aws:iam::YOUR_ACCOUNT_ID:role/YOUR_LAMBDA_ROLE \
    --region us-east-1
```

Replace:

```text
YOUR_ACCOUNT_ID
```

and:

```text
YOUR_LAMBDA_ROLE
```

with your actual values.

---

# 2.3 Test the Lambda Function

Create:

```text
event.json
```

Example:

```json
{
  "body": "{\"name\":\"Josh\",\"email\":\"josh@example.com\"}"
}
```

Invoke the function:

```bash
aws lambda invoke \
    --function-name submission-receiver \
    --payload fileb://event.json \
    response.json
```

View the response:

```bash
cat response.json
```

Expected result:

```json
{
    "statusCode": 200,
    "headers": {
        "Content-Type": "application/json"
    },
    "body": "{\"message\": \"Data successfully received and logged!\", \"id\": \"a1b2c3d4\"}"
}
```

---

# 2.4 Create the API Gateway REST API

Create a REST API using:

**AWS Console → API Gateway → REST API**

Create:

```text
API Name:
submission-api
```

Create a resource:

```text
/submit
```

Then create:

```text
POST
```

---

# 2.5 Integrate API Gateway with Lambda

For the `POST /submit` method:

```text
Integration type:
Lambda Function

Lambda:
submission-receiver
```

Enable Lambda proxy integration if available.

The request flow becomes:

```text
Client
   │
   │ POST /submit
   ▼
API Gateway
   │
   ▼
Lambda
   │
   ▼
CloudWatch Logs
```

---

# 2.6 Deploy the API

Create a stage:

```text
prod
```

Deploy the API.

Your endpoint will look similar to:

```text
https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/prod/submit
```

---

# 2.7 Test the API

Using `curl`:

```bash
curl -X POST \
https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/submit \
-H "Content-Type: application/json" \
-d '{"name":"Josh","email":"josh@example.com"}'
```

Expected response:

```json
{
    "message": "Data successfully received and logged!",
    "id": "a1b2c3d4"
}
```

---

# Step 3: CloudWatch Observability

## 3.1 Generate Traffic

Send several requests to the API:

```bash
curl -X POST \
https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/submit \
-H "Content-Type: application/json" \
-d '{"name":"User 1"}'
```

Repeat with different payloads.

Also open the ECS application URL in your browser.

---

# 3.2 Check Lambda Logs

Go to:

**AWS Console → CloudWatch → Logs → Log groups**

Find:

```text
/aws/lambda/submission-receiver
```

Open the latest log stream.

You should see:

```text
Received data: {"name":"User 1"}
```

This confirms that:

1. API Gateway received the request.
2. API Gateway invoked Lambda.
3. Lambda received the payload.
4. Lambda logged the payload.
5. CloudWatch captured the log.

---

# 3.3 Create a CloudWatch Dashboard

Go to:

**CloudWatch → Dashboards → Create dashboard**

Name it:

```text
Serverless Application Dashboard
```

Add a widget for Lambda **Invocations**.

Metric:

```text
AWS/Lambda
```

Select:

```text
FunctionName = submission-receiver
Metric = Invocations
```

Add another widget for:

```text
Errors
```

Select:

```text
AWS/Lambda
FunctionName = submission-receiver
Metric = Errors
```

Your dashboard should contain:

```text
┌─────────────────────────────────────┐
│ Lambda Invocations                  │
│                                     │
│             📈                      │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ Lambda Errors                       │
│                                     │
│             📉                      │
└─────────────────────────────────────┘
```

---

# Verification Checklist

## Containerized Application

- [ ] Docker application created
- [ ] Dockerfile created
- [ ] Docker image built
- [ ] ECR repository created
- [ ] Docker image pushed to ECR
- [ ] ECS cluster created
- [ ] ECS task definition created
- [ ] ECS Fargate service deployed
- [ ] Web application accessible

## Serverless API

- [ ] Lambda function created
- [ ] Lambda receives JSON payload
- [ ] Lambda logs payload
- [ ] Lambda generates submission ID
- [ ] API Gateway REST API created
- [ ] `/submit` resource created
- [ ] `POST` method configured
- [ ] Lambda integration configured
- [ ] API deployed to a stage
- [ ] API tested successfully

## CloudWatch

- [ ] API traffic generated
- [ ] Lambda CloudWatch logs verified
- [ ] Lambda Invocations metric added
- [ ] Lambda Errors metric added
- [ ] CloudWatch dashboard created
- [ ] Dashboard displays metrics correctly

---

# Final Architecture

After completing all three steps, the application should look like:

```text
                         INTERNET
                            │
                 ┌──────────┴──────────┐
                 │                     │
                 ▼                     ▼
          ECS Fargate              API Gateway
                 │                     │
          Docker Container             │
                 │                     ▼
                 │                  Lambda
                 │                     │
                 │                     ▼
                 │                CloudWatch
                 │                     │
                 └──────────┬──────────┘
                            │
                       Monitoring
                       & Metrics
```

---

# Useful AWS CLI Commands

### Check AWS identity

```bash
aws sts get-caller-identity
```

### List ECR repositories

```bash
aws ecr describe-repositories
```

### List ECS clusters

```bash
aws ecs list-clusters
```

### List Lambda functions

```bash
aws lambda list-functions
```

### List API Gateway APIs

```bash
aws apigateway get-rest-apis
```

### List CloudWatch log groups

```bash
aws logs describe-log-groups
```

### Check CloudFormation stacks

```bash
aws cloudformation list-stacks
```

---

# Cleanup

To avoid unnecessary AWS charges after completing the exercise, remove resources that are no longer required.

Check and clean up:

- ECS Fargate services
- ECS clusters
- Application Load Balancers
- ECR repositories/images
- Lambda functions
- API Gateway APIs
- CloudWatch dashboards/log groups
- CloudFormation stacks
- Unused Elastic IPs
- NAT Gateways
- S3 buckets/data if created

For CloudFormation-managed resources, prefer deleting the stack:

```bash
aws cloudformation delete-stack \
    --stack-name aws-ecs-web-stack \
    --region us-east-1
```

> **Warning:** Deleting resources can permanently remove data. Review the resources and dependencies before deletion.

---

# Conclusion

This project demonstrates a complete AWS deployment workflow:

**Docker → ECR → ECS/Fargate → API Gateway → Lambda → CloudWatch**

It provides practical experience with:

- Containerization
- Amazon ECR
- ECS and Fargate
- Infrastructure as Code with CloudFormation
- Serverless computing
- API Gateway
- Lambda
- CloudWatch Logs
- CloudWatch Metrics
- Application monitoring
- AWS CLI