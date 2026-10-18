# TalentFlow AI: Scalable and Secure Cloud Deployment on AWS

Built by Srinithiya M for the Davine Technologies AWS Cloud Internship (Batch 3) capstone project.

---

## What This Project Does

Davine Technologies supplied only a static recruitment dashboard (HTML, CSS, JavaScript).
On its own it has no server, no database, no security and no way to be released safely.

This project builds the complete AWS platform behind it:
- Runs the app as a container on ECS Fargate in private subnets
- Stores all candidates, jobs and interviews permanently in DynamoDB
- Serves the frontend globally over HTTPS with CloudFront and a private S3 bucket
- Sends an email alert automatically when a candidate record changes
- Scales from 1 to 3 tasks on CPU load
- Releases a new version on every git push (CI/CD)
- Protects the app with AWS WAF and monitors it with CloudWatch

---

## Architecture

```
        Users (browser)
              │ HTTPS
              ▼
   ┌───────────────────────────┐
   │  CloudFront  +  AWS WAF   │
   └───────┬───────────┬───────┘
     /*    │           │  /api/*
           ▼           ▼
   ┌────────────┐  ┌──────────────────────────────────────────┐
   │ S3 bucket  │  │ VPC 10.0.0.0/16 (2 Availability Zones)   │
   │ (private,  │  │                                          │
   │  OAC)      │  │  Public subnets:   ALB  +  NAT gateway   │
   └────────────┘  │          │                               │
                   │          ▼ port 8000                     │
                   │  Private subnets:  ECS Fargate tasks     │
                   │          │         (Flask + frontend)    │
                   └──────────┼───────────────────────────────┘
                              ▼
                   ┌────────────────────┐   Stream   ┌────────┐   ┌───────────┐
                   │ DynamoDB           │ ─────────▶ │ Lambda │──▶│ SNS email │
                   │ Candidates, Jobs,  │            └────────┘   └───────────┘
                   │ Interviews         │
                   └────────────────────┘

   CI/CD:  GitHub ─▶ CodePipeline ─▶ CodeBuild ─▶ ECR ─▶ ECS rolling deploy
   Ops:    CloudWatch (logs, dashboard, alarm)  |  CloudTrail  |  AWS Budgets
```

---

## Tech Stack and Why

| Component | Technology | Why I Chose It |
|---|---|---|
| Backend | Flask + Gunicorn (Python) | Small API with a /health endpoint and read/write endpoints for the three tables |
| Containers | Docker, Amazon ECR | One portable image holds the frontend and the API |
| Compute | ECS on AWS Fargate | No servers to manage, supports auto scaling and rolling deployments |
| Load balancer | Application Load Balancer | Health checks and traffic spread across tasks |
| Database | DynamoDB | Serverless, no maintenance, simple key-value access pattern |
| Static hosting | S3 + CloudFront (OAC) | Cheap, fast HTTPS delivery while the bucket stays private |
| Security | AWS WAF, IAM least privilege | Filters bad traffic and limits what every service can do |
| Alerts | DynamoDB Streams, Lambda, SNS | Event-driven email alerts with no extra server |
| Monitoring | CloudWatch, CloudTrail, AWS Budgets | Logs, alarm, audit trail and cost protection |
| CI/CD | GitHub, CodePipeline, CodeBuild | Push to main builds and deploys automatically |
| IaC | Terraform | Builds and destroys the network and data layer from code |

### Production Upgrade Path
| Current | At Scale |
|---|---|
| Single NAT gateway | One NAT per Availability Zone, or VPC endpoints |
| HTTP from CloudFront to ALB | HTTPS with ACM certificate and custom domain |
| Provisioned DynamoDB (1 RCU / 1 WCU) | On-demand capacity or table auto scaling |
| Demo login in the frontend | Amazon Cognito |
| Rolling deployment | Blue/green with CodeDeploy |

---

## How the Request Flow Works

1. User opens the CloudFront HTTPS URL
2. WAF inspects the request
3. Static files (index.html, style.css, script.js) come from the private S3 bucket
4. The page calls `/api/data`, CloudFront forwards `/api/*` to the ALB (no caching)
5. The ALB sends it to a Fargate task in a private subnet
6. Flask reads or writes DynamoDB and returns JSON
7. A new Candidates item triggers the stream, Lambda publishes to SNS, and an email arrives

---

## Network Design

| Resource | Details |
|---|---|
| VPC | talentflow-vpc, 10.0.0.0/16 |
| Public subnets | 10.0.1.0/24 (us-east-1a), 10.0.2.0/24 (us-east-1b) |
| Private subnets | 10.0.11.0/24 (us-east-1a), 10.0.12.0/24 (us-east-1b) |
| Gateways | 1 internet gateway, 1 NAT gateway in a public subnet |
| ALB security group | Allows HTTP 80 and HTTPS 443 from the internet |
| ECS security group | Allows port 8000 only from the ALB security group |

Application containers have no public IP and cannot be reached directly from the internet.

---

## CI/CD Pipeline

```
git push to main
      │
      ▼
CodePipeline (Source: GitHub)
      │
      ▼
CodeBuild runs buildspec.yml
   1. Log in to ECR
   2. Build the Docker image
   3. Push it tagged with the 7 character commit id
   4. Write imagedefinitions.json
      │
      ▼
Deploy stage updates the ECS service (rolling deployment, no downtime)
```

---

## Auto Scaling and Load Test

The ECS service uses a target tracking policy on average CPU (target 50%), minimum 1 task, maximum 3.

| Test (Apache Bench) | Requests | Rate | Failed | Observation |
|---|---|---|---|---|
| /api/data, concurrency 30, 300 s | 1805 | 5.79 req/s | 0 | Limited by DynamoDB 1/1 capacity and latency, CPU stayed low |
| /health, concurrency 100, 420 s | 31,817 | 75.75 req/s | 0 | Average CPU stayed under the 50% target |
| /health, concurrency 100, 420 s, CPU target lowered to 5% | 64,111 | 152.64 req/s | 0 | Scaled out from 1 to 3 tasks, then back to 1 after load stopped |

The first tests were limited by DynamoDB capacity and network latency, not CPU. The target was lowered
temporarily to prove the scaling mechanism works, then restored to 50%.

---

## Quick Start

### Run the container locally

```bash
git clone https://github.com/srinithiyadev/talentflow-aws-capstone.git
cd talentflow-aws-capstone
docker build -t talentflow-ai .
docker run -p 8000:8000 -e AWS_DEFAULT_REGION=us-east-1 talentflow-ai
```

The API needs AWS credentials with access to the Candidates, Jobs and Interviews tables.
Open http://localhost:8000 and check http://localhost:8000/health.

### Build the demo network and data layer with Terraform

```bash
cd terraform
terraform init
terraform plan
terraform apply
terraform destroy   # remove everything when done
```

This creates 18 resources (VPC, subnets, gateways, route tables, 3 DynamoDB tables, ECR repo, S3 bucket).
Names use a `tf-` prefix so they never clash with the real environment.

---

## Test Results

| Test | Result |
|---|---|
| /health on the ALB | Returns ok, target Healthy |
| GET /api/data through CloudFront | JSON returned over HTTPS |
| Add a candidate and reload | Data persists in DynamoDB |
| New candidate triggers stream | SNS email received |
| Load test | Scaled 1 to 3 tasks, then back to 1 |
| Manual CodeBuild run | Image built and pushed to ECR |
| Push to main | Pipeline Source, Build and Deploy all green |
| WAF attached | App still loads normally |
| Terraform plan, apply, destroy | 18 resources created and removed |

---

## Challenges and Fixes

| Problem | Fix |
|---|---|
| CloudFront could not be created at first | Account verification fixed through an AWS Support case |
| API returned 500 on ALB and 504 on CloudFront after rebuilding NAT and ALB | Private route table still pointed to a deleted NAT gateway (blackhole route), repointed it to the new NAT |
| Pipeline Deploy stage failed | Added ECS permissions and `iam:PassRole` for the two ECS roles to the pipeline role |
| Auto scaling did not trigger | Load was limited by latency and DynamoDB capacity, so the CPU target was lowered for the test |
| Hourly billing from NAT, ALB, Fargate and WAF | Budgets alerts, tagging, and deleting billed resources once the work was documented |

---

## Non-Functional Features

| Feature | Implementation | Benefit |
|---|---|---|
| Least privilege IAM | Separate roles for ECS execution, ECS task, Lambda, CodeBuild, CodePipeline | Each service can only do what it needs |
| Private S3 | Block public access, OAC, versioning, SSE-S3 | Only CloudFront can read the files |
| Health checks | ALB checks /health, 60 second grace period | Unhealthy tasks are replaced |
| Audit trail | Multi-region CloudTrail with log validation | Every API call is recorded |
| Cost protection | AWS Budgets with email alerts, tagging with Project=TalentFlow | No surprise bills |
| Container hardening | App runs as a non-root user in the image | Smaller attack surface |

---

## Screenshots

### VPC, Subnets and Route Tables
![VPC](docs/screenshots/vpc-subnets.png)

### ECS Service Running with Healthy Target
![ECS](docs/screenshots/ecs-service.png)

### CloudFront Origins and Behaviors
![CloudFront](docs/screenshots/cloudfront.png)

### SNS Email Alert
![Alert](docs/screenshots/sns-alert.png)

### Auto Scaling: Scale Out to 3 Tasks
![Scaling](docs/screenshots/auto-scaling.png)

### CodePipeline: All Stages Green
![Pipeline](docs/screenshots/codepipeline.png)

### AWS WAF Protection Pack
![WAF](docs/screenshots/waf.png)

### Terraform Apply and Destroy
![Terraform](docs/screenshots/terraform.png)

---

## Project Structure

```
talentflow-aws-capstone/
├── app.py              # Flask API (/health, /api/data)
├── index.html          # Frontend provided by Davine Technologies
├── style.css
├── script.js           # Frontend script, saves and loads data through /api/data
├── 1.png               # Logo
├── Dockerfile          # python:3.12-slim, Gunicorn on port 8000
├── requirements.txt
├── buildspec.yml       # CodeBuild: build, tag, push to ECR
├── iam/                # IAM policy documents
├── lambda/             # DynamoDB Stream to SNS alert function
├── terraform/          # VPC, DynamoDB, ECR and S3 demo infrastructure
└── README.md
```

---

## Limitations

- The frontend login is a demo login, not real authentication. Cognito was planned as an optional extra and not implemented.
- One NAT gateway is used to keep cost low.
- Traffic from CloudFront to the ALB uses HTTP, and there is no custom domain.
- DynamoDB uses low provisioned capacity, which limited load test throughput.
- The live environment was deleted after documentation to avoid cost, so there is no permanent demo URL. Everything can be rebuilt from this repository.

---

## Author

**Srinithiya M**
AWS Cloud Intern, Davine Technologies (Batch 3)

GitHub: https://github.com/srinithiyadev
LinkedIn: https://www.linkedin.com/in/srinithiya-m-081243291
