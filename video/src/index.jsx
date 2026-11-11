import { Composition, registerRoot } from 'remotion';
import { Lehrercockpit, LC_FRAMES } from './Lehrercockpit';
import { Einrichtung, EINRICHTUNG_FRAMES } from './Einrichtung';

const Root = () => (
  <>
    <Composition id="Lehrercockpit" component={Lehrercockpit} durationInFrames={LC_FRAMES} fps={30} width={1920} height={1080} />
    <Composition id="Einrichtung" component={Einrichtung} durationInFrames={EINRICHTUNG_FRAMES} fps={30} width={1920} height={1080} />
  </>
);

registerRoot(Root);
