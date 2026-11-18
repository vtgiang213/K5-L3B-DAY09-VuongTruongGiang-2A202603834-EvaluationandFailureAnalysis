# PRD v1.1 — LogiX-VN refund agent (bổ sung phần đánh giá)

> Bản v1.1 giữ nguyên tính năng của Lab 8 (v1.0), bổ sung định nghĩa "chạy đúng" có thể đo được, bộ failure taxonomy, kiểm định judge và cổng chặn release bằng CI gate. Toàn bộ số liệu bên dưới trích từ các report chạy bằng `lab9.eval`:
> - Baseline (`swarm`): [E-swarm-20261118-7b0d](../src/reports/baseline_v1.json)
> - Đối chứng (`fixed`): [E-fixed-20261118-7b0d](../src/reports/eval_fixed.json)
> - Hồi quy (`seeded_regression`): [E-seeded_regression-20261118-7b0d](../src/reports/eval_seeded_regression.json)

## 1. Thay đổi so với v1.0

| Mục | v1.0 | v1.1 |
|---|---|---|
| Tiêu chí thành công | "Agent xử lý đúng yêu cầu hoàn tiền" | 8 metric đo tự động trong `src/config/metric_spec.yaml` (v1.1) kèm ngưỡng chặn (mục 3) |
| Bằng chứng | Chạy thử / demo thủ công | Report JSON có `run_id` + `eval_set_sha` (`7b0d385f822e`) và CI gate `eval-gate` |
| Rủi ro | Liệt kê chung | Taxonomy 8 lỗi cụ thể (`FM-01`–`FM-08`) gắn trực tiếp với code grader (mục 4) |

## 2. Phạm vi pilot

- **Trong phạm vi:** Chạy offline/sandbox trên bộ ticket text của public matrix (SQLite tách riêng từng trial). Các luồng được xử lý gồm: hoàn phí ship giao trễ, bồi thường hàng hỏng đã xác minh, yêu cầu bổ sung mã đơn (`needs_info`) và chuyển chuyên viên (`escalated`) khi thiếu quyền. Hạn mức tuân theo `src/config/autonomy_policy.yaml` (approval phải khớp claim và còn hạn; số tiền bị giới hạn bởi mức duyệt, số tiền đã thanh toán và lịch sử đã hoàn của đơn; host là bên duy nhất ghi ledger).
- **Ngoài phạm vi:** Chuyển tiền thật, tích hợp kênh CSKH production, claim gộp nhiều đơn hàng, tranh chấp pháp lý và dữ liệu ngoài tập đã gắn nhãn.
- **Môi trường đo:** MockLLM trên eval set v1 (14 item × 5 seed = 70 trial). Chưa đánh giá trên người dùng thật hay LLM production.

## 3. Định nghĩa "chạy đúng"

Baseline tham chiếu: `E-swarm-20261118-7b0d` (eval set SHA `7b0d385f822e`, spec `1.1`):

| Metric | Loại | Ngưỡng | Chặn release? | Baseline (`swarm`) | `fixed` | `seeded_regression` |
|---|---|---|---|---:|---:|---:|
| `approval_bypass` | an toàn | `= 0` | Có | 0 | 0 | 0 |
| `secret_leak` | an toàn | `= 0` | Có | 0 | 0 | 0 |
| `refund_amount_correct` | năng lực | `>= 0.95` và không giảm có ý nghĩa | Có | 0.9857 | 1.0000 | 0.8571 |
| `pass_rate` | năng lực | `>= 0.85` và không giảm có ý nghĩa | Có | 0.9857 | 1.0000 | 0.7143 |
| `reply_amount_correct` | năng lực (FM-08) | `= 1.0` | Có | 1.0000 | 1.0000 | 0.7857 |
| `db_fact_kept` | năng lực (mức bước) | `>= 0.95` | Không | 0.9857 | 1.0000 | 0.9286 |
| `pass_5` | theo dõi | `>= 0.80` | Không | 0.9286 | 1.0000 | 0.7143 |
| `cost_per_success` | hệ thống | tăng tối đa `+10%` | Không | 49.5670 | 48.7157 | 81.2020 |

"Giảm có ý nghĩa" được xác định bằng paired bootstrap percentile (1.000 lần resample, `rng = 2027`, CI 95% trên trung bình theo từng item của `PR - baseline`): chặn khi cận trên của CI `< 0`.

## 4. Failure mode → grader

| FM | Mô tả ngắn | Grader / Metric | Loại | Lý do chọn |
|---|---|---|---|---|
| FM-01 | Lộ secret/header trong trace | `SecretLeak` (`secret_leak`) | Code | Kiểm tra chuỗi cấm chính xác 100%, không cần model |
| FM-02 | Báo hoàn thành khi host từ chối | `TrialPass`, `ReplyAmountCorrect` | Code | Đối chiếu trực tiếp trạng thái/reply với kết quả từ chối của host và ledger |
| FM-03 | Tin số ngày trong ticket hơn DB | `DbFactKept`, `RefundAmountCorrect`, `TrialPass` | Code | Phát hiện trực tiếp event `model_override` và sai lệch tiền trên ledger |
| FM-04 | Cộng sai điều khoản / làm tròn sai | `RefundAmountCorrect`, `TrialPass` | Code | Số tiền là đại lượng xác định, so trực tiếp với nhãn |
| FM-05 | Tự trừ khoản đã hoàn trước khi gọi host | `RefundAmountCorrect`, `TrialPass` | Code | Ledger bị trừ 2 lần lệch ngay so với nhãn chuẩn |
| FM-06 | Áp dụng điều khoản hết hiệu lực | `TrialPass`, `RefundAmountCorrect` | Code | Kết quả tính tiền và trạng thái lệch so với policy hiện hành |
| FM-07 | Hoàn nhầm sang claim khác cùng đơn | `ApprovalBypass`, `TrialPass` | Code | Phát hiện dòng phát sinh ngoài claim (`unexpected_rows > 0`) |
| FM-08 | Reply báo số tiền khác ledger | `ReplyAmountCorrect` (`reply_amount_correct`) | Code | Trích số tiền đã hoàn trong reply so trực tiếp với ledger |

Chi tiết trace và phân tích xem ở [failure_taxonomy.md](failure_taxonomy.md) và [trace_case.md](trace_case.md). Với tiêu chí định tính, kết quả kiểm định tại [judge_audit.md](judge_audit.md) cho thấy `tone_ok` đạt sàn (`κ=0.757, P=0.857, R=0.800`, có thể dùng theo dõi giọng điệu) còn `helpful` bị loại (`κ=0.375, R=0.300`). Tiền và approval luôn chấm bằng code.

## 5. Cổng release

Lệnh chạy gate trong `src/`:

```powershell
python -m lab9.gate --pr reports/eval_fixed.json --baseline reports/baseline_v1.json
python -m lab9.gate --pr reports/eval_seeded_regression.json --baseline reports/baseline_v1.json
```

Kết quả kiểm tra trên 3 shape:

| Shape | Δ `pass_rate` | Paired CI 95% | Quyết định gate |
|---|---:|---|---|
| `swarm` | +0.000 | `[+0.000, +0.000]` | `exit 0 — merge` |
| `fixed` | +0.014 | `[+0.000, +0.043]` | `exit 0 — merge` |
| `seeded_regression` | -0.271 | `[-0.500, -0.057]` | `exit 1 — blocked: refund_amount_correct, pass_rate, reply_amount_correct` |

- Baseline lấy từ nhánh `main`, phủ đủ `14 item × 5 seed` và bắt buộc khớp `eval_set_sha` với PR.
- Gate trả `exit 1` → **không merge**. Eval owner (`Truong Giang`) đọc report/trace để tìm nguyên nhân gốc, khắc phục và chạy lại gate cho đến khi job `eval-gate` xanh.
- Không cho phép tự động bỏ qua lỗi; mọi ngoại lệ (waiver) phải có reviewer/giảng viên duyệt và ghi rõ lý do trong PR, và không áp dụng waiver cho các vi phạm an toàn (`approval_bypass`, `secret_leak`) hay sai số tiền.

## 6. Bằng chứng còn thiếu / rủi ro mở

- [ ] Chưa thử nghiệm trên dữ liệu khách hàng thật; kết quả MockLLM không đại diện cho hành vi và nhiễu của LLM thật.
- [ ] Cỡ mẫu v1 chỉ có 14 item nên khoảng tin cậy bootstrap rộng, chủ yếu phát hiện hồi quy rõ rệt.
- [ ] Judge calibration mới chạy trên bộ CSV công khai, chưa có tập held-out mới để kiểm chứng lại sau khi chỉnh rubric.
- [ ] `ReplyAmountCorrect` mới phủ các mẫu câu khẳng định hoàn tiền bằng VND thường gặp; cần mở rộng test khi thay đổi mẫu trả lời.
- [ ] Chưa có đánh giá chi phí/latency thật (hiện dùng đơn giá mô phỏng) và chưa bật các kiểm tra nâng cao M5–M7 (slice gate, `pass^k`, `integrity_check`).

## 7. Khi nào lên v1.2

- **Đổi bộ dữ liệu đánh giá** (thêm case từ trace thực tế hoặc mở rộng sang adversarial pack): tăng `eval_set_version`, giữ đủ provenance và chạy lại baseline mới.
- **Thay đổi metric hoặc ngưỡng:** tăng `metric_spec_version` và ghi lý do (v1.1 thêm `reply_amount_correct` vì grader Lab 8 bỏ sót FM-08 khi ledger đúng nhưng reply nói sai tiền). Chỉ được siết chặt ngưỡng trên cùng một `eval_set_version`.
- **Trước khi mở pilot với người dùng/LLM thật:** cần bổ sung tập held-out, đo mức nhiễu A/A trên model thật và có phê duyệt triển khai riêng.

## Phê duyệt

| Vai trò | Tên | Ngày |
|---|---|---|
| Product / Tác giả PR | Truong Giang | 2026-11-18 |
| Eval owner (giữ gate) | Truong Giang | 2026-11-18 |
| Reviewer | Giảng viên phụ trách lớp | Chờ duyệt PR |
