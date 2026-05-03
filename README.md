# ATX Futures Tokens' Funding Rates

([English below](#english-version))

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

<video src="https://github.com/user-attachments/assets/7286d209-e0df-46ad-956d-fe963b4dbbe0" controls width="100%"></video>

<p align="center"><em>Tôi (trái) & những người đồng đội ATX ở sự kiện GM Vietnam 2025</em></p>

## 3. Setup & Run Locally

* Cài đặt và chạy [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/)

* Clone repo này về máy local:

```bash
git clone <repo-url>
cd notable-tokens-realtime-tracking
```

* Tạo folder .venv & install các libs trong requirements.txt

```
pip install -r requirements.txt
```

> Đừng nhầm với [requirements-dags.txt](requirements-dags.txt) — file đó là các package bổ sung cho các Airflow containers (`webserver` & `scheduler`) trong Docker.

* Build images và dựng các services bằng Docker Compose:

```bash
docker-compose up -d --build
```

> Lần đầu chạy sẽ mất vài phút để build images ([dags/Dockerfile](dags/Dockerfile), [consumers/Dockerfile](consumers/Dockerfile)) và pull các images còn lại. Các service khởi động theo thứ tự:
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

* Mở Airflow UI và bật DAG **`funding_rates_automation`** (mặc định bị tắt). DAG sẽ tự chạy **[15 phút](dags/kafka_stream.py#L143)**/lần với 3 tasks chạy tuần tự:

  1. **`stream_data_from_api`** — Gọi ATX API, produce funding rates vào Kafka topic `funding_rates`
  2. **`wait_for_consumer`** — `PythonSensor` poll Postgres mỗi 5 giây, chờ ít nhất 1 row mới được insert vào bảng `funding_rates` (timeout 5 phút)
  3. **`dbt_run`** — Chạy `dbt run` ngay khi consumer xử lý xong --> update view `stg_funding_rates` và bảng `fct_funding_rates`

* Chờ cho service `consumer` tự động consume data từ message queue của topic `funding_rates` --> insert data đó vào bảng `funding_rates` trong PostgreSQL.

  > **Lưu ý:** Consumer hiện đang được config [`auto_offset_reset="earliest"`](consumers/kafka_consumer.py#L49) — tức là lần đầu chạy (chưa có committed offset) sẽ đọc **toàn bộ messages từ đầu topic**. Những lần sau sẽ tiếp tục từ offset đã committed.

* Kiểm tra data đã insert vào PostgreSQL (port `5433` được expose ra host):

```bash
docker exec -it postgres_data psql -U trading -d trading -c "SELECT * FROM funding_rates ORDER BY ingested_at DESC LIMIT 20;"
```

* Chờ cho dbt tự động trigger bởi Airflow (task `dbt_run`) sau khi consumer đã insert **đủ toàn bộ records** của DAG run đó vào PostgreSQL. Sensor tracking tổng số records qua XCom — chỉ khi `COUNT(*) >= total_sent` thì `dbt_run` mới được kích hoạt. Table `fct_funding_rates` sẽ được cập nhật **1 lần/DAG run**, sau khi tất cả batches đã được consume xong.

  | Model | Materialization | Mô tả |
  |---|---|---|
  | `stg_funding_rates` | view | Lọc rows `funding_rate IS NULL`, convert `event_time` (ms) → `event_at` (timestamptz) |
  | `fct_funding_rates` | table | Thêm `funding_rate_category` theo ngưỡng `-0.3/-0.8/-1.2/-2`, thêm cờ `is_attractive` |

  Kiểm tra bảng mart:

  ```bash
  docker exec -it postgres_data psql -U trading -d trading -c "SELECT base_asset, funding_rate, funding_rate_category, is_attractive FROM fct_funding_rates ORDER BY funding_rate ASC;"
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

## Contact

Author: Phạm Quốc Hùng <br />

<a href="mailto:pham.quochung0999@gmail.com">![Gmail](https://img.shields.io/badge/Gmail-D14836?style=for-the-badge&logo=gmail&logoColor=white)</a> <a href="https://public.tableau.com/app/profile/hung.pham279">![Tableau](https://img.shields.io/badge/Tableau-E97627?style=for-the-badge&logo=Tableau&logoColor=white)</a> <a href="https://github.com/phamquochung279">![Github](https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white)</a> <a href="https://www.linkedin.com/in/pham-quochung/">![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)</a>

---

## English Version

# ATX Futures Tokens' Funding Rates

## 1. Project Flow

<a href="ATX%20Funding%20Rates%20Project%20Architecture.png" target="_blank">
  <img src="ATX%20Funding%20Rates%20Project%20Architecture.png" alt="ATX Funding Rates Project Architecture" title="ATX Funding Rates Project Architecture" width="100%">
</a>

## 2. Background Story

If you are a crypto trader or working in crypto, you must have heard of a mechanism called the *funding fees*, created to keep a token's futures price and spot price closely aligned. At its core, it works like this:

- If a token has a **positive** funding rate *(funding payment rate)*, people who are holding **Long** positions of said token must **pay funding fees** to the **Short** side.
- Conversely, if funding rates are **negative**, the **Short** side pays funding fees to the **Long** side.

So, in order to take advantage of this mechanism, experienced traders would "abuse" this strategy:
1) Find tokens with negative funding rates (can be as low as -2)
2) Open a Long position
3) Hold onto position for dear life (HODL) to earn funding fees

> At ATX, I myself witnessed an absolute legend earning **~50 million VND (~$1,900)** in funding fees after holding a Long position for **2 full weeks**. Made me think a lot about my salary and career choices.

This project is based on one of the tasks I used to do at ATX: help the Community Manager look for tokens with attractive funding rates --> if there's any, alert the "whales" (VIP traders) ASAP --> the whales are inclined trade more. Cha-ching for us.

I built this project partly to refresh my data skills, and partly as a tribute to my time in crypto with ATX. Tough but memorable days.

<video src="https://github.com/user-attachments/assets/7286d209-e0df-46ad-956d-fe963b4dbbe0" controls width="100%"></video>

<p align="center"><em>Me (left) & my ATX lads at GM Vietnam 2025</em></p>

## 3. Setup & Run Locally

* Install and run [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/)

* Clone this repository to your local machine:

```bash
git clone <repo-url>
cd notable-tokens-realtime-tracking
```

* Create the .venv folder and install libraries from requirements.txt

```
pip install -r requirements.txt
```

> Do not confuse it with [requirements-dags.txt](requirements-dags.txt) — that file contains additional packages for the Airflow containers (`webserver` & `scheduler`) in Docker.

* Build images and start services with Docker Compose:

```bash
docker-compose up -d --build
```

> The first run will take a few minutes to build images ([dags/Dockerfile](dags/Dockerfile), [consumers/Dockerfile](consumers/Dockerfile)) and pull the remaining images. Services start in this order:
> `Zookeeper` → `Kafka Broker` → `Schema Registry` + `Control Center` → `Postgres` → `Airflow Webserver` → `Airflow Scheduler` → `Kafka Consumer`

* Check that all services are healthy:

```bash
docker-compose ps
```

* Access the UIs:

| Service | URL | Credentials |
|---|---|---|
| Airflow Webserver | http://localhost:8080 | admin / admin |
| Kafka Control Center | http://localhost:9021 | _(no login required)_ |

* Open the Airflow UI and enable DAG **`funding_rates_automation`** (disabled by default). The DAG runs automatically every **[15 minutes](dags/kafka_stream.py#L143)** with 3 sequential tasks:

  1. **`stream_data_from_api`** — Call the ATX API and produce funding rates to Kafka topic `funding_rates`
  2. **`wait_for_consumer`** — `PythonSensor` polls Postgres every 5 seconds, waiting for at least 1 new row inserted into table `funding_rates` (5-minute timeout)
  3. **`dbt_run`** — Run `dbt run` right after the consumer finishes processing --> update view `stg_funding_rates` and table `fct_funding_rates`

* Wait for the `consumer` service to automatically consume data from the message queue of topic `funding_rates` --> then insert that data into table `funding_rates` in PostgreSQL.

  > **Note:** The consumer is currently configured with [`auto_offset_reset="earliest"`](consumers/kafka_consumer.py#L49) — meaning on first run (with no committed offset), it will read **all messages from the beginning of the topic**. Later runs continue from the committed offset.

* Check inserted data in PostgreSQL (port `5433` is exposed to host):

```bash
docker exec -it postgres_data psql -U trading -d trading -c "SELECT * FROM funding_rates ORDER BY ingested_at DESC LIMIT 20;"
```

* Wait for dbt to be automatically triggered by Airflow (task `dbt_run`) after the consumer has inserted **the full set of records** for that DAG run into PostgreSQL. The sensor tracks total records via XCom — only when `COUNT(*) >= total_sent` will `dbt_run` be triggered. Table `fct_funding_rates` will be updated **once per DAG run**, after all batches are fully consumed.

  | Model | Materialization | Description |
  |---|---|---|
  | `stg_funding_rates` | view | Filter rows where `funding_rate IS NULL`, convert `event_time` (ms) → `event_at` (timestamptz) |
  | `fct_funding_rates` | table | Add `funding_rate_category` by thresholds `-0.3/-0.8/-1.2/-2`, add `is_attractive` flag |

  Check mart table:

  ```bash
  docker exec -it postgres_data psql -U trading -d trading -c "SELECT base_asset, funding_rate, funding_rate_category, is_attractive FROM fct_funding_rates ORDER BY funding_rate ASC;"
  ```

* (Optional) Stop all services after use:

```bash
docker-compose down
```

> Add the `-v` flag if you also want to remove data volumes: `docker-compose down -v`

---

## 4. Notes For Running This Project In Production

### Security

- **Change all default passwords** in `docker-compose.yml` before deploying. Current values are:
  - Airflow DB: `airflow / airflow`
  - Trading DB: `trading / trading`
  - Airflow Webserver Secret Key: `this_is_a_very_secured_key`
- Do not commit credentials to Git. Use **Docker Secrets** or a `.env` file (already added to `.gitignore`).
- Do not expose port `5433` (PostgreSQL) to the public internet. Use firewall rules or allow internal network only.

### Reliability

- **Airflow Executor**: On local I am using `SequentialExecutor` (only one task runs at a time) --> in production you should switch to `LocalExecutor` or `CeleryExecutor` for parallel processing. To change executor, update **2 places** in `docker-compose.yml`: [webserver (L116)](docker-compose.yml#L116) and [scheduler (L151)](docker-compose.yml#L151).
- **Kafka Replication Factor**: Currently set to `1` (single broker, no replicas). If the broker dies, data is lost. In production, use at least 3 brokers with `replication.factor=3`.
- **Consumer restart policy**: The `consumer` service already has `restart: always` — ensuring automatic restart if it crashes.
- Add **persistent volumes** for `postgres_data` so data is not lost when containers restart:
  ```yaml
  volumes:
    - postgres_data_volume:/var/lib/postgresql/data
  ```

### Monitoring & Observability

- Kafka **Control Center** at `http://<server-ip>:9021` lets you monitor consumer lag and throughput of topic `funding_rates`.
- View Airflow task logs at `http://<server-ip>:8080` or in folder `./logs/`.
- Consider adding alerting (email, Slack, Discord, etc.) for Airflow DAG failures via `on_failure_callback` in `default_args`.

### Rate Limiting

- The ATX API currently has only 7 tokens, so `BATCH_SIZE` 10 and `BATCH_DELAY` 10s between batches are only symbolic and have no real impact on how the project runs.
- If the token count increases, adjust `BATCH_SIZE` and `BATCH_DELAY` in [dags/kafka_stream.py](dags/kafka_stream.py) to avoid IP blocking.

## Contact

Author: Phạm Quốc Hùng <br />

<a href="mailto:pham.quochung0999@gmail.com">![Gmail](https://img.shields.io/badge/Gmail-D14836?style=for-the-badge&logo=gmail&logoColor=white)</a> <a href="https://public.tableau.com/app/profile/hung.pham279">![Tableau](https://img.shields.io/badge/Tableau-E97627?style=for-the-badge&logo=Tableau&logoColor=white)</a> <a href="https://github.com/phamquochung279">![Github](https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white)</a> <a href="https://www.linkedin.com/in/pham-quochung/">![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)</a>

