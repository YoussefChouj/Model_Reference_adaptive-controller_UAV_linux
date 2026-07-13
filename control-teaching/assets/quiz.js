/* Reusable recall-check widget. Markup contract (same as lessons 1-3):
   <div class="quiz" id="quiz"> ... <div class="q">question</div>
   <div data-correct="N"><button>..</button><button>..</button></div> ...
   <p class="fb" id="fb"></p> </div>
   Include with: <script src="../assets/quiz.js"></script> (after the quiz markup). */
document.querySelectorAll('.quiz [data-correct]').forEach(function (group) {
  var correct = +group.dataset.correct;
  var btns = group.querySelectorAll('button');
  var fb = group.closest('.quiz').querySelector('.fb');
  btns.forEach(function (b, i) {
    b.addEventListener('click', function () {
      btns.forEach(function (x) { x.disabled = true; });
      if (i === correct) {
        b.classList.add('correct');
        if (fb) fb.textContent = 'Correct — retrieved from memory, not re-read.';
      } else {
        b.classList.add('wrong');
        btns[correct].classList.add('correct');
        if (fb) fb.textContent = 'Note the highlighted answer, then find the section above that proves it.';
      }
    });
  });
});
