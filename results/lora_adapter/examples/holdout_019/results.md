# holdout_019 (holdout split)

Chosen because: a figure that exists was reported as NO_FIGURE.

11 claims: 8 right, 3 wrong, 0 handed off to the TA.

| # | Sentence | Truth | Verdict | Outcome |
|---|---|---|---|---|
| 1 | As shown in Figure 1, DistilBERT reaches 57.1% test accuracy on SVHN. | error | NO_FIGURE | **wrong** |
| 2 | On IMDB, MLP is 53.2 points better than VGG-16 (Figure 1). | error | NO_FIGURE | **wrong** |
| 3 | On Fashion-MNIST, MLP obtains a test accuracy of 60%. | correct | CONSISTENT | **right** |
| 4 | DistilBERT outperforms ViT-S by 3 percentage points on IMDB. | correct | NO_FIGURE | **wrong** |
| 5 | MLP attains a accuracy of 99.9% at epoch 8. | error | MISMATCH | **right** |
| 6 | As shown in Figure 2, MLP reaches 83.1% accuracy at epoch 4. | correct | CONSISTENT | **right** |
| 7 | MLP attains a accuracy of 86.7% at epoch 3 (Figure 2). | error | MISMATCH | **right** |
| 8 | From epoch 5 to epoch 6, the accuracy of MLP improves by a relative 1.2%. | error | MISMATCH | **right** |
| 9 | As shown in Figure 3, at epoch 50, the loss of Ours is 0.422. | error | MISMATCH | **right** |
| 10 | Baseline has a loss of 0.156 at epoch 30. | error | MISMATCH | **right** |
| 11 | XGBoost reaches 78.1% accuracy on Fashion-MNIST. | no_figure | NO_FIGURE | **right** |

## Evidence for each claim

1. WRONG: figure none (true fig1); readings: none; estimate -; flag margin -; true value 59; why: no figure shows this series / x
2. WRONG: figure none (true fig1); readings: none; estimate -; flag margin -; true value 4.5; why: no figure shows this series / x
3. RIGHT: figure fig1 (true fig1); readings: ocr_pixel 59.9, vlm_crop 60; estimate 59.9; flag margin 1.23; true value 60.4; why: gap <= rounding + accept margin
4. WRONG: figure none (true fig1); readings: none; estimate -; flag margin -; true value 3.4; why: no figure shows this series / x
5. RIGHT: figure fig2 (true fig2); readings: deplot 92.6, ocr_pixel 92.7; estimate 92.7; flag margin 0.656; true value 92.8; why: gap > rounding + flag margin
6. RIGHT: figure fig2 (true fig2); readings: deplot 83, ocr_pixel 83.1; estimate 83; flag margin 0.603; true value 83.1; why: gap <= rounding + accept margin
7. RIGHT: figure fig2 (true fig2); readings: deplot 79.6, ocr_pixel 79.5; estimate 79.6; flag margin 0.578; true value 79.6; why: gap > rounding + flag margin
8. RIGHT: figure fig2 (true fig2); readings: deplot 3.33, ocr_pixel 3.27; estimate 3.3; flag margin 0.574; true value 3.21; why: gap > rounding + flag margin
9. RIGHT: figure fig3 (true fig3); readings: deplot 0.57, ocr_pixel 0.565; estimate 0.568; flag margin 0.0257; true value 0.565; why: gap > rounding + flag margin
10. RIGHT: figure fig3 (true fig3); readings: deplot 0.87, ocr_pixel 0.871; estimate 0.87; flag margin 0.0202; true value 0.87; why: gap > rounding + flag margin
11. RIGHT: figure none (true None); readings: none; estimate -; flag margin -; true value -; why: no figure shows this series / x
