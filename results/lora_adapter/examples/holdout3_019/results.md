# holdout3_019 (holdout3 split)

Chosen because: a sentence that fits two figures.

15 claims: 9 right, 1 wrong, 5 handed off to the TA.

| # | Sentence | Truth | Verdict | Outcome |
|---|---|---|---|---|
| 1 | On IMDB, Ours obtains a validation accuracy of over 75% (Figure 1). | correct | NO_FIGURE | **wrong** |
| 2 | Ours reaches 54.6% validation accuracy on SST-2 (Figure 1). | error | MISMATCH | **right** |
| 3 | On MNIST, ResNet-50 obtains a validation accuracy of 71.2%. | error | MISMATCH | **right** |
| 4 | Transformer achieves 68.0% validation accuracy on MNIST. | correct | NOT_SURE | **handed off** |
| 5 | On IMDB, LSTM obtains a validation accuracy of 44.3%. | correct | CONSISTENT | **right** |
| 6 | On IMDB, LSTM obtains a validation accuracy of 2.6%. | error | NOT_SURE | **handed off** |
| 7 | LSTM scores 17.3 points higher on MNIST than on CIFAR-10. | correct | NOT_SURE | **handed off** |
| 8 | On MNIST, BERT-base is 4.3 points better than LSTM (Figure 3). | correct | NOT_SURE | **handed off** |
| 9 | As shown in Figure 3, BERT-base reaches 77.0% accuracy on AG News. | correct | CONSISTENT | **right** |
| 10 | BERT-base achieves 75.2% accuracy on AG News (Figure 3). | error | MISMATCH | **right** |
| 11 | On IMDB, LSTM obtains a accuracy of 55.9%. | error | NOT_SURE | **handed off** |
| 12 | ViT-S outperforms Transformer by 52.4 percentage points on SVHN (Figure 4). | error | MISMATCH | **right** |
| 13 | MLP achieves 71.0% test accuracy on SVHN. | error | MISMATCH | **right** |
| 14 | MLP reaches 87% test accuracy on MNIST (Figure 4). | correct | CONSISTENT | **right** |
| 15 | As shown in Figure 4, on SVHN, MLP obtains a test accuracy of 67.6%. | error | MISMATCH | **right** |

## Evidence for each claim

1. WRONG: figure none (true fig1); readings: none; estimate -; flag margin -; true value 78; why: no figure shows this series / x
2. RIGHT: figure fig1 (true fig1); readings: ocr_pixel 74.1, vlm_crop 75; estimate 74.5; flag margin 2.14; true value 74.6; why: gap > rounding + flag margin
3. RIGHT: figure fig2 (true fig1); readings: deplot 72.5, vlm_table 72.5; estimate 72.5; flag margin 0.93; true value 61.2; why: gap > rounding + flag margin
4. HANDED OFF: figure fig4 (true fig1); readings: deplot 87.2, vlm_crop 88; estimate 87.6; flag margin 2.01; true value 68; why: ambiguous figure: fig4, fig1
5. RIGHT: figure fig2 (true fig2); readings: deplot 44.3, vlm_table 44.3; estimate 44.3; flag margin 0.93; true value 44.3; why: gap <= rounding + accept margin
6. HANDED OFF: figure fig2 (true fig2); readings: deplot 44.3, vlm_table 44.3; estimate 44.3; flag margin 0.93; true value 44.3; why: ambiguous figure: fig2, fig3
7. HANDED OFF: figure fig2 (true fig2); readings: deplot 17.3, vlm_table 17.3; estimate 17.3; flag margin 0.93; true value 17.3; why: ambiguous figure: fig2, fig3
8. HANDED OFF: figure fig3 (true fig3); readings: none; estimate -; flag margin -; true value 4.3; why: handed off: no trustworthy pair among the tools still available on this figure
9. RIGHT: figure fig3 (true fig3); readings: deplot 77.5, vlm_table 76.5; estimate 77; flag margin 2.23; true value 77; why: gap <= rounding + accept margin
10. RIGHT: figure fig3 (true fig3); readings: deplot 77.5, vlm_crop 77, vlm_table 76.5; estimate 77; flag margin 1.68; true value 77; why: gap > rounding + flag margin
11. HANDED OFF: figure fig2 (true fig3); readings: deplot 44.3, vlm_table 44.3; estimate 44.3; flag margin 0.93; true value 65.9; why: ambiguous figure: fig2, fig3
12. RIGHT: figure fig4 (true fig4); readings: deplot 2.4, vlm_table 0.1; estimate 1.25; flag margin 3.67; true value 2.4; why: gap > rounding + flag margin
13. RIGHT: figure fig4 (true fig4); readings: deplot 66.3, vlm_table 66.9; estimate 66.6; flag margin 1.78; true value 66; why: gap > rounding + flag margin
14. RIGHT: figure fig4 (true fig4); readings: deplot 87.7, vlm_table 84.3; estimate 86; flag margin 4.9; true value 86.8; why: gap <= rounding + accept margin
15. RIGHT: figure fig4 (true fig4); readings: deplot 66.3, ocr_pixel 65.1, vlm_crop 65, vlm_table 66.9; estimate 65.7; flag margin 1.03; true value 66; why: gap > rounding + flag margin
