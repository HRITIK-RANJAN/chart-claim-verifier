# holdout_011 (holdout split)

Chosen because: a wrongly flagged claim.

15 claims: 8 right, 1 wrong, 6 handed off to the TA.

| # | Sentence | Truth | Verdict | Outcome |
|---|---|---|---|---|
| 1 | At epoch 5, MobileNet achieves 81.3% accuracy. | correct | CONSISTENT | **right** |
| 2 | MLP reaches over 55% accuracy at epoch 2. | correct | CONSISTENT | **right** |
| 3 | As shown in Figure 1, MobileNet reaches over 80% accuracy at epoch 5. | correct | CONSISTENT | **right** |
| 4 | At epoch 4, BERT-base is 6.7 points better than MobileNet. | error | NOT_SURE | **handed off** |
| 5 | As shown in Figure 2, Ours reaches about 70% F1 score at epoch 34. | correct | NOT_SURE | **handed off** |
| 6 | At epoch 24, ViT-S achieves 93.5% F1 score. | correct | NOT_SURE | **handed off** |
| 7 | At epoch 28, MobileNet achieves 70.0% F1 score. | error | NOT_SURE | **handed off** |
| 8 | VGG-16 has a loss of 1.545 at epoch 8. | error | NOT_SURE | **handed off** |
| 9 | At epoch 14, the loss of CNN is 1.470 (Figure 3). | error | MISMATCH | **right** |
| 10 | CNN has a loss of 0.371 at epoch 30. | correct | MISMATCH | **wrong** |
| 11 | At epoch 14, the loss of EfficientNet is 0.990. | error | NOT_SURE | **handed off** |
| 12 | As shown in Figure 4, from epoch 10 to epoch 20, the test accuracy of BERT-base improves by a relative 19.1%. | correct | CONSISTENT | **right** |
| 13 | As shown in Figure 4, at epoch 20, MobileNet is 3.3 points better than BERT-base. | correct | CONSISTENT | **right** |
| 14 | From epoch 15 to epoch 25, the test accuracy of CNN improves by a relative 11.2%. | error | MISMATCH | **right** |
| 15 | Random Forest reaches 70.2% accuracy on SVHN. | no_figure | NO_FIGURE | **right** |

## Evidence for each claim

1. RIGHT: figure fig1 (true fig1); readings: deplot 81.5, ocr_pixel 81.3; estimate 81.4; flag margin 0.565; true value 81.3; why: gap <= rounding + accept margin
2. RIGHT: figure fig1 (true fig1); readings: deplot 57.8, ocr_pixel 57.9; estimate 57.8; flag margin 0.518; true value 57.9; why: gap <= rounding + accept margin
3. RIGHT: figure fig1 (true fig1); readings: deplot 81.5, ocr_pixel 81.3; estimate 81.4; flag margin 0.565; true value 81.3; why: gap <= rounding + accept margin
4. HANDED OFF: figure fig1 (true fig1); readings: deplot 4.09, ocr_pixel 4.04; estimate 4.06; flag margin 0.551; true value 4.2; why: ambiguous figure: fig1, fig4
5. HANDED OFF: figure fig2 (true fig2); readings: none; estimate -; flag margin -; true value 71.1; why: handed off: no trustworthy pair among the tools still available on this figure
6. HANDED OFF: figure fig2 (true fig2); readings: none; estimate -; flag margin -; true value 93.5; why: handed off: no trustworthy pair among the tools still available on this figure
7. HANDED OFF: figure fig2 (true fig2); readings: none; estimate -; flag margin -; true value 75.3; why: handed off: no trustworthy pair among the tools still available on this figure
8. HANDED OFF: figure fig3 (true fig3); readings: none; estimate -; flag margin -; true value 1.18; why: handed off: no trustworthy pair among the tools still available on this figure
9. RIGHT: figure fig3 (true fig3); readings: deplot 0.54, ocr_pixel 0.545; estimate 0.543; flag margin 0.0222; true value 0.545; why: gap > rounding + flag margin
10. WRONG: figure fig3 (true fig3); readings: deplot 0.43, vlm_crop 0.45; estimate 0.44; flag margin 0.036; true value 0.371; why: gap > rounding + flag margin
11. HANDED OFF: figure fig3 (true fig3); readings: deplot 0.62, vlm_crop 0.95; estimate 0.785; flag margin 0.325; true value 0.62; why: handed off: decision still unclear and no usable tool left (vlm_table agrees wrongly with vlm_crop 5.1% of the time)
12. RIGHT: figure fig4 (true fig4); readings: deplot 19.1, ocr_pixel 19; estimate 19.1; flag margin 0.345; true value 19.1; why: gap <= rounding + accept margin
13. RIGHT: figure fig4 (true fig4); readings: deplot 3.29, ocr_pixel 3.36; estimate 3.33; flag margin 0.43; true value 3.3; why: gap <= rounding + accept margin
14. RIGHT: figure fig4 (true fig4); readings: deplot 9.82, ocr_pixel 10.2; estimate 10; flag margin 0.608; true value 10.1; why: gap > rounding + flag margin
15. RIGHT: figure none (true None); readings: none; estimate -; flag margin -; true value -; why: no figure shows this series / x
