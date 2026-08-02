.PHONY: build run clean test

BINARY_NAME=ktown-server
GO=go

build:
	$(GO) build -o $(BINARY_NAME) cmd/server

run:
	$(GO) run cmd/server

clean:
	rm -f $(BINARY_NAME)

test:
	$(GO) test ./...

deps:
	$(GO) mod tidy

fmt:
	$(GO) fmt ./...