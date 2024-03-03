# FIRST STAGE: GO BUILD
FROM golang:1.21.6 as build

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY *.go ./

RUN CGO_ENABLED=0 GOOS=linux go build -o /matrix-bridge

# SECOND AND FINAL STAGE
FROM scratch

COPY --from=build /matrix-bridge /matrix-bridge

CMD ["/matrix-bridge"]

