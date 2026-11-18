# Trace case: từ trace tới quyết định sai đầu tiên

Lệnh tái hiện (chạy trong `src/`):

```powershell
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11
python -m pytest -q -m student -o addopts= tests/test_lab9_trace_case.py
```

## Tóm tắt case (`C-002@11`)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11` (item `E-002`, report `E-seeded_regression-20261118-384c`, trace `R-seeded_regression-C-002-s11`) |
| Triệu chứng | `TrialPass`, `RefundAmountCorrect`, `DbFactKept` đều `False` (Lab 8 báo `status resolved != denied`). Ledger ghi hoàn `20.000đ` và reply cũng báo `20.000đ`, trong khi nhãn chuẩn là `denied`, `0đ`. |
| Bước sai đầu tiên | Event 3 (`model_override`): `{"delay_days": 5}` — agent lấy số ngày trễ trong ticket ghi đè dữ liệu DB (`delay_days=2`). |
| Vì sao là bước *đầu tiên* | Event 1 (`handoff`) giữ đúng claim `C-002` và quyền `owner_order_only`; event 2 (`investigator`) truy vấn DB trả đúng `delay_days=2`. Sai lệch chỉ bắt đầu ở event 3, kéo theo quote `20.000đ` ở event 4 và khoản hoàn sai ở cuối. |
| Failure mode | `FM-03` (`ticket_trust`, layer `orchestration/state`) — xem [failure_taxonomy.md](failure_taxonomy.md). |
| Đối chứng | Trên `fixed` (`R-fixed-C-002-s11`), event 1–2 giống hệt (`delay_days=2`), không có `model_override`; bước 3 quote `0đ` (`no_entitlement`), bước 4 từ chối, ledger `0đ`, trạng thái `denied`. |
| Regression test | `test_c002_ticket_cannot_override_database` trong [test_lab9_trace_case.py](../src/tests/test_lab9_trace_case.py) chạy trên cả `seeded_regression` và `fixed`: kiểm tra 3 grader (`DbFactKept`, `RefundAmountCorrect`, `TrialPass`) cùng fail trên `seeded_regression` và pass trên `fixed`. |
| Chưa chắc chắn | Trace chạy bằng MockLLM và chỉ là 1 claim ở 1 seed. Kết quả chứng minh chuỗi sai từ `model_override` đến ledger trên dữ liệu mô phỏng, nhưng chưa thể đánh giá tần suất xảy ra trên LLM thật hoặc các biến thể khác trong `seeded_regression`. |

## Đối chiếu ledger trước reply

| Trường | `seeded_regression` | `fixed` | Label |
|---|---:|---:|---:|
| `refund_vnd` | 20000 | 0 | 0 |
| `refund_count` | 1 | 0 | 0 |
| `status` | `resolved` | `denied` | `denied` |
| `unexpected_rows` | 0 | 0 | 0 |

Lưu ý: ở case này reply khớp với số tiền thực ghi trong ledger (20.000đ) nên không phải FM-08, và approval hợp lệ nên không phải `approval_bypass`. Do `host_recomputes_entitlement=false`, host chỉ kiểm tra approval/cap mà không tính lại điều kiện hưởng từ DB, khiến lỗi dữ liệu đầu vào đi thẳng xuống ledger.

## Chi tiết từng bước trong trace lỗi

| Bước | Event | Chi tiết |
|---:|---|---|
| 1 | `handoff` | Đúng claim `C-002`, quyền `owner_order_only`, chỉ cấp tool đọc và tính tiền. |
| 2 | `investigator` | DB trả `delay_days=2` (nguồn dữ liệu chuẩn). |
| 3 | `model_override` | `{"delay_days": 5}` — **bước sai đầu tiên**, tin số ngày trong ticket thay vì DB. |
| 4 | `quote` | `amount_vnd=20000`, `SHIP-LATE-03` (hệ quả từ bước 3). |
| 5 | `refund_history` | Lịch sử hoàn `0đ`. |
| 6 | `reply` | `Dạ, LogiX đã hoàn 20.000đ cho đơn O-202.` |

Vì `C-002` đã có sẵn trong `eval_set_v1.jsonl` (`E-002`), mình bổ sung regression test riêng ở [test_lab9_trace_case.py](../src/tests/test_lab9_trace_case.py) thay vì thêm dòng trùng lặp làm đổi SHA của eval set v1.
