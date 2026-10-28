# holdout_018 (holdout split)

Chosen because: a wrongly flagged claim.

13 claims: 11 right, 2 wrong, 0 handed off to the TA.

| # | Sentence | Truth | Verdict | Outcome |
|---|---|---|---|---|
| 1 | DistilBERT reaches about 80% F1 score at epoch 7. | correct | CONSISTENT | **right** |
| 2 | As shown in Figure 1, from epoch 14 to epoch 15, the F1 score of MobileNet improves by a relative 2.9%. | correct | MISMATCH | **wrong** |
| 3 | CNN reaches 75.0% F1 score at epoch 8 (Figure 1). | correct | MISMATCH | **wrong** |
| 4 | As shown in Figure 1, MobileNet outperforms ResNet-18 by 11.2 percentage points at epoch 1. | error | MISMATCH | **right** |
| 5 | MobileNet outperforms Ours by 11 percentage points at epoch 10. | correct | CONSISTENT | **right** |
| 6 | At epoch 50, Ours is 11.2 points better than MobileNet. | error | MISMATCH | **right** |
| 7 | From epoch 40 to epoch 50, the F1 score of Ours improves by a relative 1.7% (Figure 2). | error | MISMATCH | **right** |
| 8 | Ours attains a F1 score of 102.9% at epoch 40. | error | MISMATCH | **right** |
| 9 | As shown in Figure 3, DistilBERT reaches over 80% test accuracy on Fashion-MNIST. | correct | CONSISTENT | **right** |
| 10 | CNN outperforms DistilBERT by about 8 percentage points on AG News. | correct | CONSISTENT | **right** |
| 11 | DistilBERT reaches about 60% test accuracy on AG News. | correct | CONSISTENT | **right** |
| 12 | On AG News, CNN is 18.0 points better than DistilBERT. | error | MISMATCH | **right** |
| 13 | SVM reaches 54.2% accuracy on Yelp. | no_figure | NO_FIGURE | **right** |

## Evidence for each claim

1. RIGHT: figure fig1 (true fig1); readings: deplot 77.2, ocr_pixel 77.5; estimate 77.3; flag margin 1.06; true value 77.3; why: gap <= rounding + accept margin
2. WRONG: figure fig1 (true fig1); readings: vlm_crop 1.22, vlm_table 0.247; estimate 0.733; flag margin 1.99; true value 2.86; why: gap > rounding + flag margin
3. WRONG: figure fig1 (true fig1); readings: vlm_crop 77, vlm_table 76.8; estimate 76.9; flag margin 0.939; true value 75; why: gap > rounding + flag margin
4. RIGHT: figure fig1 (true fig1); readings: deplot 21.2, vlm_table 22.5; estimate 21.9; flag margin 2.86; true value 20.9; why: gap > rounding + flag margin
5. RIGHT: figure fig2 (true fig2); readings: deplot 11, ocr_pixel 11; estimate 11; flag margin 0.676; true value 11; why: gap <= rounding + accept margin
6. RIGHT: figure fig2 (true fig2); readings: deplot 3.48, ocr_pixel 3.63; estimate 3.55; flag margin 0.849; true value 3.6; why: gap > rounding + flag margin
7. RIGHT: figure fig2 (true fig2); readings: deplot 2.34, ocr_pixel 2.67, vlm_table 2.62; estimate 2.62; flag margin 0.439; true value 2.63; why: gap > rounding + flag margin
8. RIGHT: figure fig2 (true fig2); readings: deplot 83.9, vlm_table 84.1; estimate 84; flag margin 0.736; true value 83.8; why: gap > rounding + flag margin
9. RIGHT: figure fig3 (true fig3); readings: deplot 83, ocr_pixel 82.7; estimate 82.9; flag margin 1.4; true value 82.7; why: gap <= rounding + accept margin
10. RIGHT: figure fig3 (true fig3); readings: deplot 7.9, ocr_pixel 8.01; estimate 7.95; flag margin 1.24; true value 8; why: gap <= rounding + accept margin
11. RIGHT: figure fig3 (true fig3); readings: deplot 56.5, ocr_pixel 56.2; estimate 56.4; flag margin 1.41; true value 56.2; why: gap <= rounding + accept margin
12. RIGHT: figure fig3 (true fig3); readings: deplot 7.9, ocr_pixel 8.01; estimate 7.95; flag margin 1.24; true value 8; why: gap > rounding + flag margin
13. RIGHT: figure none (true None); readings: none; estimate -; flag margin -; true value -; why: no figure shows this series / x
