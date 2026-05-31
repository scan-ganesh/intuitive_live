#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

# =====================================================================
# CONFIGURATION VARIABLE DEFINITIONS
# =====================================================================
REGION="asia-south1"
JOB_NAME="nifty-straddle-job"

# Network resource names generated automatically
VPC_NAME="trading-vpc-network"
SUBNET_NAME="trading-subnet-mumbai"
SUBNET_CIDR="10.10.0.0/24"

ROUTER_NAME="trading-nat-router"
NAT_GATEWAY_NAME="trading-nat-gateway"
STATIC_IP_NAME="sebi-trading-static-ip"

echo "========== Starting SEBI Compliance Network Setup =========="
echo "Target Job: $JOB_NAME"
echo "Target Region: $REGION"
echo "------------------------------------------------------------"

# 1. Create a dedicated Custom VPC Network
echo "[1/6] Creating Custom VPC Network: $VPC_NAME..."
gcloud compute networks create $VPC_NAME \
    --subnet-mode=custom \
    --bgp-routing-mode=regional

# 2. Create a Subnet inside the VPC in Mumbai
echo "[2/6] Creating Subnet in asia-south1: $SUBNET_NAME ($SUBNET_CIDR)..."
gcloud compute networks subnets create $SUBNET_NAME \
    --network=$VPC_NAME \
    --range=$SUBNET_CIDR \
    --region=$REGION

# 3. Reserve a Static External IP address
echo "[3/6] Reserving a Static External IPv4 Address..."
gcloud compute addresses create $STATIC_IP_NAME \
    --region=$REGION

# Fetch and store the allocated IP for confirmation
ALLOCATED_IP=$(gcloud compute addresses describe $STATIC_IP_NAME --region=$REGION --format="value(address)")
echo "SUCCESS: Allocated Static IP is: $ALLOCATED_IP"

# 4. Create the Cloud Router
echo "[4/6] Creating Cloud Router: $ROUTER_NAME..."
gcloud compute routers create $ROUTER_NAME \
    --network=$VPC_NAME \
    --region=$REGION

# 5. Create Cloud NAT and bind the Static IP (With Optimized Port Settings)
echo "[5/6] Creating Cloud NAT Gateway with Dynamic Port Allocation..."
gcloud compute routers nats create $NAT_GATEWAY_NAME \
    --router=$ROUTER_NAME \
    --region=$REGION \
    --nat-custom-subnet-ip-ranges=$SUBNET_NAME \
    --nat-external-ip-pool=$STATIC_IP_NAME \
    --enable-dynamic-port-allocation

# 6. Update the Cloud Run Job configuration to enforce outbound traffic routing
echo "[6/6] Connecting Cloud Run Job '$JOB_NAME' to the VPC network via Direct Egress..."
gcloud run jobs update $JOB_NAME \
    --region=$REGION \
    --network=$VPC_NAME \
    --subnet=$SUBNET_NAME \
    --vpc-egress=all-traffic

echo "------------------------------------------------------------"
echo "========== Configuration Successfully Deployed! =========="
echo "Give this IP to your stockbroker for SEBI whitelisting:"
echo ">>>>> $ALLOCATED_IP <<<<<"
echo "============================================================"