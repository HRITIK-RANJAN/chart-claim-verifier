# test_002 (test split)

Chosen because: the report with the most claims (test).

15 claims: 15 right, 0 wrong, 0 handed off to the TA.

| # | Sentence | Truth | Verdict | Outcome |
|---|---|---|---|---|
| 1 | EfficientNet reaches 60.1% accuracy at epoch 40. | correct | CONSISTENT | **right** |
| 2 | EfficientNet reaches 94.5% accuracy at epoch 70. | error | MISMATCH | **right** |
| 3 | As shown in Figure 1, EfficientNet reaches 65.7% accuracy at epoch 70. | correct | CONSISTENT | **right** |
| 4 | At epoch 11, BERT-base achieves 76.2% F1 score. | correct | CONSISTENT | **right** |
| 5 | As shown in Figure 2, BERT-base reaches 70.6% F1 score at epoch 3. | correct | CONSISTENT | **right** |
| 6 | As shown in Figure 2, DistilBERT attains a F1 score of 54.1% at epoch 2. | error | MISMATCH | **right** |
| 7 | ResNet-50 reaches 77.4% F1 score at epoch 10. | error | MISMATCH | **right** |
| 8 | On SVHN, ViT-S obtains a F1 score of 68.1%. | correct | CONSISTENT | **right** |
| 9 | BERT-base achieves 82.1% F1 score on MNIST. | error | MISMATCH | **right** |
| 10 | ResNet-18 achieves over 70% F1 score on SVHN (Figure 3). | correct | CONSISTENT | **right** |
| 11 | As shown in Figure 4, CNN outperforms BERT-base by 21.5 percentage points on CIFAR-10. | error | MISMATCH | **right** |
| 12 | On AG News, LSTM obtains a validation accuracy of 53.1%. | error | MISMATCH | **right** |
| 13 | As shown in Figure 4, CNN achieves 66.0% validation accuracy on AG News. | error | MISMATCH | **right** |
| 14 | GRU achieves 94% validation accuracy on CIFAR-10 (Figure 4). | correct | CONSISTENT | **right** |
| 15 | On Tiny-ImageNet, XGBoost obtains an accuracy of 81.2%. | no_figure | NO_FIGURE | **right** |

## Evidence for each claim

1. RIGHT: figure fig1 (true fig1); readings: deplot 60.2, ocr_pixel 60.2; estimate 60.2; flag margin 0.83; true value 60.1; why: gap <= rounding + accept margin
2. RIGHT: figure fig1 (true fig1); readings: deplot 65.8, ocr_pixel 65.7; estimate 65.8; flag margin 0.904; true value 65.7; why: gap > rounding + flag margin
3. RIGHT: figure fig1 (true fig1); readings: deplot 65.8, ocr_pixel 65.7; estimate 65.8; flag margin 0.904; true value 65.7; why: gap <= rounding + accept margin
4. RIGHT: figure fig2 (true fig2); readings: deplot 76.1, vlm_crop 77; estimate 76.5; flag margin 1.88; true value 76.2; why: gap <= rounding + accept margin
5. RIGHT: figure fig2 (true fig2); readings: deplot 70.9, ocr_pixel 70.8; estimate 70.8; flag margin 0.806; true value 70.6; why: gap <= rounding + accept margin
6. RIGHT: figure fig2 (true fig2); readings: ocr_pixel 64.2, vlm_crop 68, vlm_table 56; estimate 64.2; flag margin 6.82; true value 63.6; why: gap > rounding + flag margin
7. RIGHT: figure fig2 (true fig2); readings: vlm_crop 89, vlm_table 85; estimate 87; flag margin 6.11; true value 89.3; why: gap > rounding + flag margin
8. RIGHT: figure fig3 (true fig3); readings: ocr_pixel 67.1, vlm_crop 70; estimate 68.6; flag margin 4.31; true value 68.1; why: gap <= rounding + accept margin
9. RIGHT: figure fig3 (true fig3); readings: vlm_crop 78, vlm_table 78; estimate 78; flag margin 1.11; true value 80.1; why: gap > rounding + flag margin
10. RIGHT: figure fig3 (true fig3); readings: deplot 76.2, vlm_table 73.9; estimate 75.1; flag margin 3.67; true value 75.9; why: gap <= rounding + accept margin
11. RIGHT: figure fig4 (true fig4); readings: deplot 1.7, ocr_pixel 1.37; estimate 1.54; flag margin 1.48; true value 1.5; why: gap > rounding + flag margin
12. RIGHT: figure fig4 (true fig4); readings: deplot 58.8, vlm_crop 58; estimate 58.4; flag margin 2; true value 58.1; why: gap > rounding + flag margin
13. RIGHT: figure fig4 (true fig4); readings: deplot 71.1, vlm_crop 70; estimate 70.5; flag margin 2.34; true value 71; why: gap > rounding + flag margin
14. RIGHT: figure fig4 (true fig4); readings: deplot 93.8, vlm_crop 92; estimate 92.9; flag margin 3.12; true value 93.6; why: gap <= rounding + accept margin
15. RIGHT: figure none (true None); readings: none; estimate -; flag margin -; true value -; why: no figure shows this series / x
