import { useContext } from 'react';
import { LayoutEditContext } from '../context/LayoutEditContext';

export const useLayoutEditContext = () => useContext(LayoutEditContext);
