locals {
  tables = ["Candidates", "Jobs", "Interviews"]
}

resource "aws_dynamodb_table" "tables" {
  for_each     = toset(local.tables)
  name         = "tf-${each.key}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
}

resource "aws_ecr_repository" "app" {
  name                 = "tf-talentflow-ai"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_s3_bucket" "frontend" {
  bucket        = "tf-talentflow-frontend-872575360511"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket                  = aws_s3_bucket.frontend.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
