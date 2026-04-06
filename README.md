# ATX Futures Tokens' Funding Rates

## 1. Project Flow

<a href="ATX%20Funding%20Rates%20Project%20Architecture.png" target="_blank">
  <img src="ATX%20Funding%20Rates%20Project%20Architecture.png" alt="ATX Funding Rates Project Architecture" title="ATX Funding Rates Project Architecture" width="100%">
</a>

## 2. Background Story

Trong crypto futures có 1 cơ chế là *phí funding* để giúp giá futures & giá spot của 1 token (coin) luôn bám sát nhau. Ngắn gọn mà nói cơ chế này hoạt động như sau:

- Nếu 1 token có funding rate *(tỷ lệ chi trả phí funding)* là **dương** --> những người đang **Long** token đó phải **trả phí funding** cho những người đang **Short**.
- Ngược lại, funding rates **âm** --> phe **Short** trả phí funding cho phe **Long**.

Vì vậy, để tận dụng cơ chế này, các traders nhiều kinh nghiệm thường có "bài" là:
1) Tìm các token đang có funding rates âm (thấp nhất là -2)
2) Vào lệnh Long
3) Hold lệnh càng lâu càng tốt để kiếm phí funding fee

> Ở sàn ATX từng có 1 trường hợp kiếm **~50 triệu VND** tiền phí funding sau khi "ngâm" 1 lệnh Long **suốt 2 tuần liền**. Khiến tôi có phần chạnh lòng khi nghĩ về đồng lương của mình.

Project này dựa trên 1 task cũ của tôi ở ATX: giúp community manager "săn lùng" các tokens đang có funding rates tốt --> loan tin tới các "cá mập" (khách hàng VIP) nhanh nhất có thể --> thúc đẩy các vị này trade nhiều hơn.

Tôi làm project này vừa để ôn lại skill, vừa để lưu giữ những kỷ niệm 1 thời trong ngành crypto cùng ATX. Những ngày gian khổ nhưng đáng nhớ.

<video src="20250208171938_upload.mp4" controls width="100%"></video>

<p align="center"><em>Tôi (trái) & những người đồng đội ATX ở sự kiện GM Vietnam 2025</em></p>

## 3. Setup & Run Locally

* Cài đặt [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/)

* Clone repo về máy:

```bash
git clone <repo-url>
cd notable-tokens-realtime-tracking
```

* Tạo folder .venv & install các libs trong requirements.txt

```
pip install -r requirements.txt
```

Đừng nhầm với [requirements-dags.txt](requirements-dags.txt) — file này là các package bổ sung cho các Airflow containers (`webserver` & `scheduler`) trong Docker.

* Dựng các services bằng Docker Compose:

```bash
docker-compose up -d
```

> Lần đầu chạy sẽ mất vài phút để pull images. Các service khởi động theo thứ tự:
> `Zookeeper` → `Kafka Broker` → `Schema Registry` + `Control Center` → `Postgres` → `Airflow Webserver` → `Airflow Scheduler` → `Kafka Consumer`

* Kiểm tra tất cả services đã healthy:

```bash
docker-compose ps
```

* Truy cập các UI:

| Service | URL | Credentials |
|---|---|---|
| Airflow Webserver | http://localhost:8080 | admin / admin |
| Kafka Control Center | http://localhost:9021 | _(không cần đăng nhập)_ |

* Trong Airflow UI, bật DAG **`funding_rates_automation`** (mặc định bị tắt). DAG sẽ tự chạy **[1 phút](dags/kafka_stream.py#L133)**/lần, gọi ATX API → produce vào Kafka topic `funding_rates`.

* Service `consumer` tự động consume messages từ message queue của topic `funding_rates` --> insert vào PostgreSQL (`postgres_data`).

  > **Lưu ý:** Consumer hiện đang được config [`auto_offset_reset="earliest"`](consumers/kafka_consumer.py#L49) — tức là lần đầu chạy (chưa có committed offset) sẽ đọc **toàn bộ messages từ đầu topic**. Những lần sau sẽ tiếp tục từ offset đã committed.

* Kiểm tra data đã insert vào PostgreSQL (port `5433` được expose ra host):

```bash
docker exec -it postgres_data psql -U trading -d trading -c "SELECT * FROM funding_rates ORDER BY ingested_at DESC LIMIT 20;"
```

* (Optional) Dừng toàn bộ services sau khi dùng xong:

```bash
docker-compose down
```

> Thêm flag `-v` nếu muốn xóa luôn data volumes: `docker-compose down -v`

---

## 4. Lưu ý khi chạy project trên Production

### Security

- **Đổi toàn bộ mật khẩu mặc định** trong `docker-compose.yml` trước khi deploy. Hiện tại đang dùng:
  - Airflow DB: `airflow / airflow`
  - Trading DB: `trading / trading`
  - Airflow Webserver Secret Key: `this_is_a_very_secured_key`
- Không commit credentials lên Git. Dùng **Docker Secrets** hoặc file `.env` (đã thêm vào `.gitignore`).
- Không expose port `5433` (PostgreSQL) ra public internet. Dùng firewall hoặc chỉ cho phép internal network.

### Reliability

- **Airflow Executor**: Trên local tôi đang dùng `SequentialExecutor` (chỉ chạy 1 task tại 1 thời điểm) --> trên production nên chuyển sang `LocalExecutor` hoặc `CeleryExecutor` để xử lý song song. Để đổi executor cần đổi ở **2 chỗ** trong `docker-compose.yml`: [webserver (L116)](docker-compose.yml#L116) và [scheduler (L151)](docker-compose.yml#L151).
- **Kafka Replication Factor**: Hiện đang set `1` (single broker, không có replica). Nếu broker chết thì mất data. Trên production cần ít nhất 3 brokers với `replication.factor=3`.
- **Consumer restart policy**: Service `consumer` đã có `restart: always` — đảm bảo tự khởi động lại nếu crash.
- Thêm **persistent volumes** cho `postgres_data` để data không bị mất khi container restart:
  ```yaml
  volumes:
    - postgres_data_volume:/var/lib/postgresql/data
  ```

### Monitoring & Observability

- Kafka **Control Center** tại `http://<server-ip>:9021` cho phép theo dõi consumer lag, throughput của topic `funding_rates`.
- Xem Airflow task logs tại `http://<server-ip>:8080` hoặc trong thư mục `./logs/`.
- Cân nhắc thêm alerting (email, Slack, Discord, v.v.) cho Airflow khi DAG fail, thông qua `on_failure_callback` trong `default_args`.

### Rate Limiting

- ATX API hiện chỉ còn 7 tokens nên `BATCH_SIZE` 10 và `BATCH_DELAY` 10s giữa các batch chỉ để tượng trưng, không có ảnh hưởng thực tế đến cách project hoạt động.
- Nếu số lượng token tăng lên, cần điều chỉnh `BATCH_SIZE` và `BATCH_DELAY` trong [dags/kafka_stream.py](dags/kafka_stream.py) để tránh bị block IP.
