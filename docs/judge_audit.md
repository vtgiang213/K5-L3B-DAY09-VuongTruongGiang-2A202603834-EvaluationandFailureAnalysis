# Judge audit

Lệnh chạy từ `src/` (dùng dữ liệu replay công khai, `FAIL` là lớp dương):

```powershell
python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 10
python -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 5
python -m pytest -q -m student -o addopts= tests/test_lab9_stats.py tests/test_lab9_calibration.py -k "not paired_bootstrap"
```

## Kết quả calibration

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---:|---:|---:|---:|---|---|
| `tone_ok` | 100 | 0.757 | 0.857 | 0.800 | Có (đạt cả 3 sàn) | **Dùng được** cho tiêu chí giọng điệu trong phạm vi tập đã kiểm định; cần kiểm thêm trên held-out trước khi đưa vào gate chính |
| `helpful` | 100 | 0.375 | 1.000 | 0.300 | Không (κ và Recall dưới sàn) | **Loại khỏi gate**; cần sửa rubric và calibration lại |

Ma trận nhầm lẫn và hiệu chỉnh Rogan-Gladen:

| Tiêu chí | TP | FP | FN | TN | Accuracy | Tỉ lệ FAIL quan sát | Tỉ lệ FAIL sau Rogan-Gladen |
|---|---:|---:|---:|---:|---:|---:|---:|
| `tone_ok` | 24 | 4 | 6 | 66 | 0.900 | 0.280 | 0.300 |
| `helpful` | 9 | 0 | 21 | 70 | 0.790 | 0.090 | 0.300 |

- Với `tone_ok`: `specificity = 66/70`, tỷ lệ hiệu chỉnh `(0.28 + 66/70 - 1) / (0.8 + 66/70 - 1) = 0.300`.
- Với `helpful`: `specificity = 1.0`, tỷ lệ hiệu chỉnh `0.09 / 0.30 = 0.300`.
- Hiệu chỉnh Rogan-Gladen chỉ ước lượng lại tỉ lệ lỗi tổng thể, không sửa được nhãn sai của từng item và không làm judge `helpful` đạt chuẩn để bật gate.

## Audit thủ công các case bất đồng (15 case)

Đối chiếu nội dung `reply` và `note` trong hai file CSV (`10` case của `tone_ok` và `5` case của `helpful`):

| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú & hành động sửa rubric |
|---:|---|---|---|---|---|
| 1 | tone `H-008` | PASS | FAIL | Người đúng | Câu dùng "Em ... nha ... check giúp em", quá suồng sã. Bổ sung ví dụ phân biệt giọng thân thiện với giọng suồng sã thay vì chỉ bắt từ lịch sự. |
| 2 | tone `H-017` | PASS | FAIL | Người đúng | Xưng "bạn ơi ... rồi nha" với khách lớn tuổi (theo note). Cần truyền thêm ngữ cảnh xưng hô cho judge và quy định mặc định dùng "anh/chị" khi chưa rõ tuổi. |
| 3 | tone `H-029` | PASS | FAIL | Người đúng | Có câu "Không cần nhắn thêm" mang giọng ra lệnh dù mở đầu có "Dạ, vui lòng". Rubric cần yêu cầu chấm toàn câu và thêm ví dụ câu từ mang tính ngăn cản khách. |
| 4 | tone `H-042` | FAIL | PASS | Người đúng | Câu ngắn nhưng đủ thông tin hoàn tiền và thời gian nhận; judge phạt oan vì thiếu lời xin lỗi. Ghi rõ trong rubric không bắt buộc xin lỗi ở mọi phản hồi và không phạt câu ngắn. |
| 5 | tone `H-051` | FAIL | PASS | Người đúng | Từ "refund" thuộc danh sách thuật ngữ CS được phép dùng. Thêm bảng từ mượn chấp nhận được vào prompt để judge không tự cấm tiếng Anh. |
| 6 | tone `H-063` | PASS | FAIL | Người đúng | Câu có lời hứa "sẽ hoàn thêm" ngoài kết quả hệ thống. Tách kiểm tra giọng điệu khỏi tính đúng nghiệp vụ; cam kết tiền bạc phải kiểm bằng code đối chiếu ledger. |
| 7 | tone `H-070` | PASS | FAIL | Người đúng | Dùng emoji cười trong tình huống khách khiếu nại. Bổ sung quy tắc xét emoji theo ngữ cảnh khiếu nại, tránh thấy "Dạ ... ạ" là cho PASS. |
| 8 | tone `H-081` | FAIL | PASS | Judge đúng (theo note, cần xác minh thêm) | Câu trả lời tách riêng trông khá lịch sự, nhưng note ghi người gán nhãn đọc nhầm ticket. Cần rà soát lại cùng ngữ cảnh ticket gốc trước khi cập nhật bộ nhãn chuẩn. |
| 9 | tone `H-088` | FAIL | PASS | Người đúng | Lặp nhẹ "Dạ, dạ" chỉ là lỗi gõ nhỏ, chưa đến mức lỗi tone. Định nghĩa rõ mức độ lỗi chính tả/gõ phím nào mới bị đánh FAIL. |
| 10 | tone `H-094` | PASS | FAIL | Người đúng | Câu trả lời mất dấu tiếng Việt hoàn toàn. Nêu rõ yêu cầu bắt buộc tiếng Việt có dấu và phân biệt lỗi mất dấu toàn câu với lỗi typo đơn lẻ. |
| 11 | helpful `HL-015` | PASS | FAIL | Người đúng | Reply báo hoàn 55.000đ nhưng ledger là 40.000đ. Lỗi sai số tiền phải kiểm bằng code đọc ledger, không để judge ngôn ngữ tự đánh giá. |
| 12 | helpful `HL-016` | PASS | FAIL | Người đúng | Reply dài, xin lỗi nhiều nhưng báo sai số tiền (55.000đ thay vì 35.000đ). Thêm cặp ví dụ cùng lỗi tiền nhưng khác độ dài để tránh judge thiên vị câu dài, lễ phép. |
| 13 | helpful `HL-035` | PASS | FAIL | Người đúng | Reply nói hoàn 50.000đ (ledger 35.000đ) và lặp lời xin lỗi. Rubric cần yêu cầu kiểm tính chính xác kết quả trước, diễn đạt xếp sau. |
| 14 | helpful `HL-043` | PASS | FAIL | Người đúng | Reply nói hoàn 35.000đ (ledger 20.000đ), lặp lời xin lỗi. Tách tiêu chí hữu ích khỏi độ đúng số tiền; mọi kiểm tra tiền dùng code grader. |
| 15 | helpful `HL-047` | PASS | FAIL | Người đúng | Câu "Ok bạn ... xử lý rồi nhé" vừa sai phong cách CS vừa thiếu thông tin đã xử lý cụ thể gì. Thêm ví dụ yêu cầu câu trả lời phải nêu rõ hành động/kết quả cụ thể. |

## Kết luận

- **Loại `helpful` khỏi gate:** Dù `Precision = 1.0` và `Accuracy = 0.79`, judge chỉ bắt được `9/30` lỗi (`Recall = 0.30`, `κ = 0.375`), bỏ sót tới `21/30` case lỗi (70%). Accuracy cao chỉ vì lớp PASS chiếm 70% tập dữ liệu. Phần lớn case bỏ sót là các câu dài, xin lỗi lịch sự nhưng báo sai tiền — cho thấy judge bị đánh lừa bởi hình thức trình bày.
- **Phạm vi dùng `tone_ok`:** Đạt cả ba sàn (`κ = 0.757`, `P = 0.857`, `R = 0.800`), vẫn còn 6 FN và 4 FP. Có thể dùng để theo dõi chất lượng giọng điệu, nhưng không dùng để kiểm tra số tiền hay quyền approval (các phần này dùng code grader ở M3).
- **Rủi ro còn lại:**
  - Cả hai bảng kết quả đều chạy trên dữ liệu replay công khai (100 case/tiêu chí), chưa có tập held-out mới để kiểm tra khả năng tổng quát hóa sau khi sửa rubric.
  - Nhãn người vẫn có thể có sai sót (như `H-081`), nên cần quy trình đối chiếu lại với ngữ cảnh gốc khi gặp bất đồng.
  - Công thức Rogan-Gladen giả định sensitivity/specificity giữ ổn định trên tập mới; khi phân phối dữ liệu đổi cần calibration lại.
