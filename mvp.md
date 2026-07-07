
there are two core functions

the minimal approach:

1. upload book as pdf docx epub etc
   a. we have sth like baidu ocr for this
2. process it so that it can be input to tts

3. tts


the mvp

4. user can pre train voice

5. api receives string returns audio in users voice

6. this works in spa and eng

7. is performant, live interpretint ready. this is the crown of the app.

8. all of this is done locally using repos and local model that work perfomnatly with this rig, knowing that perhaps we only habe about 60% ram and cpu since the interpreting platform per se uses a bunch.


bonus:
api can receive books and process them, return an estimate and then the audio
app can split book into chapters so audiobook is more manageable
api can ocr books, images : i send batch of images and app tries to guess name : send stained glass : probably x saint.
api can generate images from a prompt. this might require me having lm studio running, idk yet, but we can probably have workaround



future :::
. app can stream local videos and books