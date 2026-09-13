import { useMemo } from 'react'
import bodyImage from './assets/body.png'
import needleImage from './assets/needle.png'
import eyesImage from './assets/eyes.png'
import eyesHappyImage from './assets/eyes-happy.png'
import eyesErrorImage from './assets/eyes-error.png'

export type CompassMode = 'idle' | 'wink' | 'happy' | 'searching' | 'error' | 'logo'

interface NavieCompassProps {
  mode?: CompassMode
  className?: string
}

export function NavieCompass({ mode = 'idle', className = '' }: NavieCompassProps) {
  const classes = useMemo(() => {
    const base = 'navie-stage'
    return mode === 'idle' ? base : `${base} navie-${mode}`
  }, [mode])

  return (
    <div className={`${classes} ${className}`.trim()} aria-label={`Navie compass mode: ${mode}`}>
      <div className="navie-body-wrap navie-fill">
        <img src={bodyImage} alt="Navie body" />
      </div>

      <div className="navie-needle-wrap navie-fill">
        <img src={needleImage} alt="Navie needle" />
      </div>

      <div className="navie-eyes-wrap navie-fill">
        <div className="navie-wink-eyes navie-fill">
          <img className="navie-eye-half navie-eye-left" src={eyesImage} alt="Navie eyes" />
          <img className="navie-eye-half navie-eye-right" src={eyesImage} alt="Navie eyes" />
        </div>

        <img className="navie-eyes-happy navie-fill" src={eyesHappyImage} alt="Navie happy eyes" />
        <img className="navie-eyes-error navie-fill" src={eyesErrorImage} alt="Navie error eyes" />
      </div>
    </div>
  )
}
