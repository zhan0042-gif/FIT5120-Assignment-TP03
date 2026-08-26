# Nginx

This directory is reserved for the future production reverse-proxy configuration. The likely single-EC2 layout will route `/` to the Vue frontend and `/api` to FastAPI, with MySQL accessible only to application services through the Docker network.

Domains, HTTPS certificates, production addresses, and the final Nginx configuration will be added after the frontend and deployment environment are defined.
